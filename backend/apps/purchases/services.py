"""
Atomic purchase posting.

Creates the bill, line items, new inventory lots, optional vendor payment,
and vendor payable ledger. Stock is written only through InventoryService.
"""

from __future__ import annotations

from decimal import Decimal

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.core.numbering import document_number_service
from apps.inventory.models import StockMovementType
from apps.inventory.services import inventory_service
from apps.payments.models import LedgerEntryType, PartyType
from apps.payments.services import ledger_service, payment_service
from apps.products.models import Product
from apps.purchases.models import Purchase, PurchaseItem, PurchaseReturn, PurchaseReturnItem
from apps.vendors.models import Vendor


class PurchaseService:
    """Purchase invoices and purchase returns."""

    def create_purchase(self, payload: dict) -> Purchase:
        items = payload.get("items") or []
        if not items:
            raise ValidationError({"items": "At least one line is required."})
        vendor = Vendor.objects.get(pk=payload["vendor_id"])
        with transaction.atomic():
            number = document_number_service.next_number("PURCHASE")
            purchase = Purchase.objects.create(
                vendor=vendor,
                bill_number=number,
                bill_date=payload.get("bill_date") or timezone.localdate(),
                payment_terms=payload.get("payment_terms") or vendor.payment_terms,
                notes=payload.get("notes", ""),
                payment_method=payload.get("payment_method", ""),
            )
            subtotal = Decimal("0")
            gst_total = Decimal("0")
            for row in items:
                product = Product.objects.select_for_update().get(pk=row["product_id"])
                qty = Decimal(str(row["quantity"]))
                if qty <= 0:
                    raise ValidationError({"quantity": "Quantity must be greater than zero."})
                list_price = Decimal(str(row.get("base_purchase_price") or row.get("list_purchase_price")))
                disc_pct = Decimal(str(row.get("supplier_discount_percent") or 0))
                disc_amt = Decimal(str(row.get("supplier_discount_amount") or 0))
                cost = inventory_service.effective_cost(
                    list_price=list_price,
                    discount_percent=disc_pct,
                    discount_amount=disc_amt,
                )
                gst_rate = Decimal(str(row.get("gst_rate") if row.get("gst_rate") is not None else product.gst_rate))
                line = qty * cost
                gst = (line * gst_rate / Decimal("100")).quantize(Decimal("0.01"))
                batch = inventory_service.create_batch(
                    product=product,
                    vendor=vendor,
                    quantity=qty,
                    list_purchase_price=list_price,
                    supplier_discount_percent=disc_pct,
                    supplier_discount_amount=disc_amt,
                    selling_price=Decimal(str(row["selling_price"])) if row.get("selling_price") is not None else None,
                    safe_selling_price=(
                        Decimal(str(row["safe_selling_price"])) if row.get("safe_selling_price") is not None else None
                    ),
                    maximum_discount_percent=(
                        Decimal(str(row["maximum_discount_percent"]))
                        if row.get("maximum_discount_percent") is not None
                        else None
                    ),
                    mrp=Decimal(str(row["mrp"])) if row.get("mrp") is not None else None,
                    pricing_mode=row.get("pricing_mode") or "NEW",
                    pricing_confirmed=bool(row.get("pricing_confirmed", False)),
                    invoice_reference=payload.get("vendor_invoice_number", "") or number,
                    purchase_date=purchase.bill_date,
                    notes=row.get("notes", ""),
                    movement_type=StockMovementType.PURCHASE,
                )
                PurchaseItem.objects.create(
                    purchase=purchase,
                    product=product,
                    batch=batch,
                    quantity=qty,
                    base_purchase_price=list_price,
                    supplier_discount_percent=disc_pct,
                    supplier_discount_amount=disc_amt,
                    effective_purchase_cost=cost,
                    mrp=batch.mrp,
                    selling_price=batch.selling_price,
                    safe_selling_price=batch.safe_selling_price,
                    maximum_customer_discount_percent=batch.maximum_discount_percent,
                    gst_rate=gst_rate,
                    gst_amount=gst,
                    line_total=line + gst,
                    pricing_mode=batch.pricing_mode,
                    notes=row.get("notes", ""),
                )
                subtotal += line
                gst_total += gst
            header_discount = Decimal(str(payload.get("discount_amount") or 0))
            other = Decimal(str(payload.get("other_charges") or 0))
            purchase.subtotal = subtotal
            purchase.discount_amount = header_discount
            purchase.taxable_amount = subtotal - header_discount
            purchase.gst_amount = gst_total
            purchase.other_charges = other
            purchase.grand_total = purchase.taxable_amount + gst_total + other
            purchase.amount_paid = Decimal(str(payload.get("amount_paid") or 0))
            purchase.save()
            ledger_service.post(
                party_type=PartyType.VENDOR,
                party_id=vendor.id,
                entry_type=LedgerEntryType.PURCHASE,
                credit=purchase.grand_total,
                reference_type="purchase",
                reference_id=purchase.id,
                notes=purchase.bill_number,
                entry_date=purchase.bill_date,
            )
            if purchase.amount_paid > 0:
                payment_service.create_payment(
                    {
                        "party_type": PartyType.VENDOR,
                        "party_id": vendor.id,
                        "amount": purchase.amount_paid,
                        "method": purchase.payment_method or "CASH",
                        "reference": purchase.bill_number,
                        "payment_date": purchase.bill_date,
                    }
                )
            return purchase

    def create_return(self, purchase: Purchase, items: list[dict], notes: str = "") -> PurchaseReturn:
        if not items:
            raise ValidationError({"items": "Return lines required."})
        with transaction.atomic():
            ret = PurchaseReturn.objects.create(
                purchase=purchase,
                return_number=document_number_service.next_number("PURCHASE_RETURN"),
                return_date=timezone.localdate(),
                notes=notes,
            )
            total = Decimal("0")
            for row in items:
                original = purchase.items.select_related("product", "batch").get(pk=row["purchase_item_id"])
                qty = Decimal(str(row["quantity"]))
                if qty <= 0 or qty > original.quantity:
                    raise ValidationError({"quantity": "Cannot return more than purchased."})
                if original.batch:
                    inventory_service.apply_movement(
                        batch=original.batch,
                        movement_type=StockMovementType.PURCHASE_RETURN,
                        quantity_delta=-qty,
                        notes=ret.return_number,
                        reference_type="purchase_return",
                        reference_id=str(ret.id),
                    )
                line = (qty * original.effective_purchase_cost).quantize(Decimal("0.01"))
                PurchaseReturnItem.objects.create(
                    purchase_return=ret,
                    purchase_item=original,
                    quantity=qty,
                    line_total=line,
                )
                total += line
            ret.grand_total = total
            ret.save()
            ledger_service.post(
                party_type=PartyType.VENDOR,
                party_id=purchase.vendor_id,
                entry_type=LedgerEntryType.PURCHASE_RETURN,
                debit=total,
                reference_type="purchase_return",
                reference_id=ret.id,
                notes=ret.return_number,
            )
            return ret


purchase_service = PurchaseService()
