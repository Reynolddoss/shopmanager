"""
Inventory helpers that never silently change stock or pricing.

Batch creation always inserts a new lot. Previous lots stay frozen so the owner
can compare cost and selling prices. Quantity changes go through apply_movement
inside a transaction, recording quantity before and after.
"""

from __future__ import annotations

from decimal import Decimal

from django.db import transaction
from django.db.models import Avg, Min, QuerySet
from rest_framework.exceptions import ValidationError

from apps.core.services import audit_service
from apps.inventory.models import InventoryBatch, StockMovement, StockMovementType
from apps.products.models import Product, ProductVendor
from apps.vendors.models import Vendor


class InventoryService:
    """Batch creation, previous-lot detection, vendor caches, and movement-backed qty."""

    def previous_batches(self, product: Product) -> QuerySet[InventoryBatch]:
        """Return older lots for a product, newest first (for pricing comparison)."""
        return InventoryBatch.objects.filter(product=product).order_by("-purchase_date", "-id")

    def latest_previous_batch(self, product: Product, *, excluding_id: int | None = None) -> InventoryBatch | None:
        """The most recent batch the owner can copy prices from."""
        qs = self.previous_batches(product)
        if excluding_id is not None:
            qs = qs.exclude(pk=excluding_id)
        return qs.first()

    def compare_with_previous(self, product: Product, new_cost: Decimal) -> dict:
        """Build the previous-batch banner payload. Does not change any prices."""
        previous = self.latest_previous_batch(product)
        if previous is None:
            return {"previous": None, "detected": False}
        cost_diff = new_cost - previous.purchase_cost
        percent = (
            (cost_diff / previous.purchase_cost * Decimal("100"))
            if previous.purchase_cost
            else Decimal("0")
        )
        return {
            "detected": True,
            "previous": {
                "id": previous.pk,
                "lot_code": previous.lot_code,
                "vendor_id": previous.vendor_id,
                "vendor_name": previous.vendor.name if previous.vendor_id else "",
                "purchase_date": previous.purchase_date,
                "purchase_cost": str(previous.purchase_cost),
                "selling_price": str(previous.selling_price),
                "safe_selling_price": str(previous.safe_selling_price),
                "maximum_discount_percent": str(previous.maximum_discount_percent),
                "remaining_quantity": str(previous.remaining_quantity),
            },
            "new_cost": str(new_cost),
            "cost_difference": str(cost_diff),
            "cost_percent_change": str(percent.quantize(Decimal("0.01"))),
        }

    def resolve_pricing(
        self,
        *,
        product: Product,
        pricing_mode: str,
        pricing_confirmed: bool,
        selling_price: Decimal | None,
        safe_selling_price: Decimal | None,
        maximum_discount_percent: Decimal | None,
        mrp: Decimal | None,
        bulk_price: Decimal | None,
    ) -> dict:
        """Apply the owner's explicit pricing mode. Never invent selling prices."""
        previous = self.latest_previous_batch(product)
        mode = (pricing_mode or "NEW").upper()
        if previous is not None and not pricing_confirmed:
            raise ValidationError(
                {"pricing_confirmed": "Previous batch detected. Confirm pricing mode before saving."}
            )
        if mode == "PREVIOUS":
            if previous is None:
                raise ValidationError({"pricing_mode": "No previous batch exists to copy."})
            return {
                "mrp": previous.mrp,
                "selling_price": previous.selling_price,
                "safe_selling_price": previous.safe_selling_price,
                "maximum_discount_percent": previous.maximum_discount_percent,
                "bulk_price": previous.bulk_price,
                "pricing_mode": "PREVIOUS",
            }
        if mode == "COPY_EDIT":
            if previous is None:
                raise ValidationError({"pricing_mode": "No previous batch exists to copy."})
            return {
                "mrp": mrp if mrp is not None else previous.mrp,
                "selling_price": selling_price if selling_price is not None else previous.selling_price,
                "safe_selling_price": (
                    safe_selling_price if safe_selling_price is not None else previous.safe_selling_price
                ),
                "maximum_discount_percent": (
                    maximum_discount_percent
                    if maximum_discount_percent is not None
                    else previous.maximum_discount_percent
                ),
                "bulk_price": bulk_price if bulk_price is not None else previous.bulk_price,
                "pricing_mode": "COPY_EDIT",
            }
        if selling_price is None or safe_selling_price is None or maximum_discount_percent is None:
            raise ValidationError(
                {"pricing": "New pricing requires selling_price, safe_selling_price, and maximum_discount_percent."}
            )
        return {
            "mrp": mrp or Decimal("0"),
            "selling_price": selling_price,
            "safe_selling_price": safe_selling_price,
            "maximum_discount_percent": maximum_discount_percent,
            "bulk_price": bulk_price,
            "pricing_mode": "NEW",
        }

    def effective_cost(
        self,
        *,
        list_price: Decimal,
        discount_percent: Decimal,
        discount_amount: Decimal,
    ) -> Decimal:
        """Derive effective purchase cost from list price and supplier discounts."""
        percent_off = (list_price * discount_percent / Decimal("100")).quantize(Decimal("0.01"))
        cost = list_price - percent_off - discount_amount
        if cost < 0:
            raise ValidationError({"purchase_cost": "Effective cost cannot be negative."})
        return cost

    def margin_snapshot(self, *, cost: Decimal, selling: Decimal, safe: Decimal, max_discount: Decimal) -> dict:
        """Display-only margin maths. Never written back as a silent price change."""
        gross = selling - cost
        percent = (gross / selling * Decimal("100")) if selling else Decimal("0")
        discounted = selling * (Decimal("1") - max_discount / Decimal("100"))
        return {
            "gross_margin": str(gross),
            "margin_percent": str(percent.quantize(Decimal("0.01"))),
            "price_after_max_discount": str(discounted.quantize(Decimal("0.01"))),
            "safe_selling_price": str(safe),
            "below_safe_if_max_discount": discounted < safe,
        }

    @transaction.atomic
    def create_batch(
        self,
        *,
        product: Product,
        vendor: Vendor | None,
        quantity: Decimal,
        list_purchase_price: Decimal,
        supplier_discount_percent: Decimal = Decimal("0"),
        supplier_discount_amount: Decimal = Decimal("0"),
        purchase_date=None,
        invoice_reference: str = "",
        lot_code: str = "",
        pricing_mode: str = "NEW",
        pricing_confirmed: bool = False,
        selling_price: Decimal | None = None,
        safe_selling_price: Decimal | None = None,
        maximum_discount_percent: Decimal | None = None,
        mrp: Decimal | None = None,
        bulk_price: Decimal | None = None,
        notes: str = "",
        movement_type: str = StockMovementType.PURCHASE,
    ) -> InventoryBatch:
        """Insert a new historical lot. Existing batches are never updated."""
        if quantity <= 0:
            raise ValidationError({"quantity": "Quantity must be greater than zero."})
        first_lot = self.latest_previous_batch(product) is None
        prices = self.resolve_pricing(
            product=product,
            pricing_mode=pricing_mode,
            pricing_confirmed=pricing_confirmed or first_lot,
            selling_price=selling_price,
            safe_selling_price=safe_selling_price,
            maximum_discount_percent=maximum_discount_percent,
            mrp=mrp,
            bulk_price=bulk_price,
        )
        cost = self.effective_cost(
            list_price=list_purchase_price,
            discount_percent=supplier_discount_percent,
            discount_amount=supplier_discount_amount,
        )
        code = lot_code or self._next_lot_code(product)
        batch = InventoryBatch.objects.create(
            product=product,
            vendor=vendor,
            lot_code=code,
            purchase_date=purchase_date,
            invoice_reference=invoice_reference,
            list_purchase_price=list_purchase_price,
            supplier_discount_percent=supplier_discount_percent,
            supplier_discount_amount=supplier_discount_amount,
            purchase_cost=cost,
            mrp=prices["mrp"],
            selling_price=prices["selling_price"],
            safe_selling_price=prices["safe_selling_price"],
            maximum_discount_percent=prices["maximum_discount_percent"],
            bulk_price=prices["bulk_price"],
            remaining_quantity=quantity,
            original_quantity=quantity,
            is_open=True,
            pricing_mode=prices["pricing_mode"],
            pricing_confirmed=True,
            notes=notes,
        )
        StockMovement.objects.create(
            product=product,
            batch=batch,
            movement_type=movement_type,
            quantity=quantity,
            quantity_before=Decimal("0"),
            quantity_after=quantity,
            reason="Batch created",
            reference_type="inventory_batch",
            reference_id=str(batch.pk),
        )
        if vendor is not None:
            self.refresh_vendor_cache(product, vendor)
        audit_service.record(
            action="batch_create",
            entity="inventory_batch",
            entity_id=batch.pk,
            new_data={"lot_code": batch.lot_code, "purchase_cost": str(batch.purchase_cost)},
        )
        return batch

    def _next_lot_code(self, product: Product) -> str:
        count = InventoryBatch.objects.filter(product=product).count() + 1
        return f"B{count:03d}"

    def refresh_vendor_cache(self, product: Product, vendor: Vendor) -> ProductVendor:
        """Rebuild convenience caches from historical batches (source of truth)."""
        lots = InventoryBatch.objects.filter(product=product, vendor=vendor).order_by("-purchase_date", "-id")
        latest = lots.first()
        aggregates = lots.aggregate(lowest=Min("purchase_cost"), average=Avg("purchase_cost"))
        link, _created = ProductVendor.objects.get_or_create(product=product, vendor=vendor)
        link.last_purchase_price = latest.purchase_cost if latest else None
        link.last_purchase_date = latest.purchase_date if latest else None
        link.lowest_historical_purchase_price = aggregates["lowest"]
        link.average_purchase_price = aggregates["average"]
        link.save()
        return link

    @transaction.atomic
    def apply_movement(
        self,
        *,
        batch: InventoryBatch,
        movement_type: str,
        quantity_delta: Decimal,
        notes: str = "",
        reason: str = "",
        reference_type: str = "",
        reference_id: str = "",
    ) -> StockMovement:
        """Adjust remaining_quantity and insert a StockMovement in one transaction."""
        before = batch.remaining_quantity
        after = before + quantity_delta
        if after < 0:
            raise ValueError("Insufficient batch quantity.")
        batch.remaining_quantity = after
        batch.is_open = after > 0
        batch.save(update_fields=["remaining_quantity", "is_open", "updated_at"])
        movement = StockMovement.objects.create(
            product=batch.product,
            batch=batch,
            movement_type=movement_type,
            quantity=quantity_delta,
            quantity_before=before,
            quantity_after=after,
            reason=reason,
            notes=notes,
            reference_type=reference_type,
            reference_id=reference_id,
        )
        audit_service.record(
            action="stock_movement",
            entity="inventory_batch",
            entity_id=batch.pk,
            new_data={
                "movement_type": movement_type,
                "quantity": str(quantity_delta),
                "before": str(before),
                "after": str(after),
            },
        )
        return movement

    def stock_status(self, product: Product, on_hand: Decimal) -> str:
        if on_hand <= 0:
            return "out_of_stock"
        threshold = product.reorder_level or product.min_stock_quantity
        if threshold and on_hand <= threshold:
            return "low_stock"
        return "in_stock"

    def allocate_fifo(self, product: Product, quantity: Decimal) -> list[tuple[InventoryBatch, Decimal]]:
        """
        Reserve quantity from oldest open lots.

        Callers must run this inside transaction.atomic() and then apply_movement.
        """
        remaining = quantity
        allocations: list[tuple[InventoryBatch, Decimal]] = []
        lots = InventoryBatch.objects.select_for_update().filter(
            product=product,
            remaining_quantity__gt=0,
        ).order_by("purchase_date", "id")
        for lot in lots:
            take = min(lot.remaining_quantity, remaining)
            allocations.append((lot, take))
            remaining -= take
            if remaining == 0:
                break
        if remaining > 0:
            raise ValidationError({"quantity": f"Insufficient stock for {product.sku}."})
        return allocations

    def allocate_batch(
        self, product: Product, quantity: Decimal, batch_id: int
    ) -> list[tuple[InventoryBatch, Decimal]]:
        """
        Reserve quantity from one chosen lot (shopkeeper override of FIFO).

        The lot must belong to the product and hold enough remaining quantity.
        """
        batch = (
            InventoryBatch.objects.select_for_update()
            .filter(pk=batch_id, product=product, remaining_quantity__gt=0)
            .first()
        )
        if batch is None:
            raise ValidationError({"batch_id": f"Lot not found or empty for {product.sku}."})
        if quantity > batch.remaining_quantity:
            raise ValidationError(
                {
                    "quantity": (
                        f"Lot {batch.lot_code} only has {batch.remaining_quantity} left "
                        f"for {product.sku}; asked for {quantity}."
                    )
                }
            )
        return [(batch, quantity)]

    def open_lots_for_billing(self, product: Product) -> list[dict]:
        """Lots with stock, oldest first — same order FIFO would use."""
        lots = InventoryBatch.objects.filter(product=product, remaining_quantity__gt=0).select_related("vendor").order_by(
            "purchase_date",
            "id",
        )
        return list(
            map(
                lambda batch: {
                    "id": batch.pk,
                    "lot_code": batch.lot_code,
                    "vendor_name": batch.vendor.name if batch.vendor_id else "",
                    "purchase_date": str(batch.purchase_date) if batch.purchase_date else "",
                    "remaining_quantity": str(batch.remaining_quantity),
                    "purchase_cost": str(batch.purchase_cost),
                    "selling_price": str(batch.selling_price),
                    "safe_selling_price": str(batch.safe_selling_price),
                    "mrp": str(batch.mrp),
                    "maximum_discount_percent": str(batch.maximum_discount_percent),
                },
                lots,
            )
        )


inventory_service = InventoryService()
