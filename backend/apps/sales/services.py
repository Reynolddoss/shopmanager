"""
Atomic sale posting with FIFO allocation.

Safe-price warnings are ValidationError details unless the owner overrides.
GST is exclusive of selling price using the product GST rate.
"""

from __future__ import annotations

from decimal import Decimal

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.core.models import ApplicationSettings
from apps.core.numbering import document_number_service
from apps.core.services import audit_service
from apps.customers.models import Customer
from apps.inventory.models import StockMovementType
from apps.inventory.services import inventory_service
from apps.payments.models import LedgerEntryType, PartyType, Payment
from apps.payments.services import ledger_service, payment_service
from apps.products.models import Product
from apps.sales.models import Sale, SaleItem, SaleReturn, SaleReturnItem


class InvoicePayloadService:
    """JSON invoice payload used later by A4 / thermal printers."""

    def for_sale(self, sale: Sale) -> dict:
        settings_row = ApplicationSettings.objects.filter(singleton_key=1).first()
        items = [
            {
                "sku": line.product.sku,
                "name": line.product.name,
                "specification": line.product.specification or "",
                "hsn": line.product.hsn_code,
                "quantity": str(line.quantity),
                "unit_price": str(line.unit_price),
                "mrp": str(line.batch.mrp if line.batch_id else 0),
                "discount": str(line.discount_amount),
                "resulting_price": str(line.resulting_price),
                "gst_rate": str(line.gst_rate),
                "gst_amount": str(line.gst_amount),
                "line_total": str(line.line_total),
            }
            for line in sale.items.select_related("product", "batch")
        ]
        due = sale.grand_total - sale.amount_paid
        return {
            "kind": "sale",
            "shop_name": settings_row.shop_name if settings_row else "",
            "shop_gstin": settings_row.gstin if settings_row else "",
            "shop_address": settings_row.address if settings_row else "",
            "shop_phone": settings_row.phone if settings_row else "",
            "invoice_number": sale.invoice_number,
            "invoice_date": str(sale.invoice_date),
            "customer": sale.customer.name if sale.customer_id else "Walk-in",
            "customer_gstin": sale.customer.gstin if sale.customer_id else "",
            "items": items,
            "subtotal": str(sale.subtotal),
            "discount_amount": str(sale.discount_amount),
            "gst_amount": str(sale.gst_amount),
            "grand_total": str(sale.grand_total),
            "amount_paid": str(sale.amount_paid),
            "amount_due": str(due),
            "amount_tendered": str(sale.amount_tendered),
            "change_given": str(sale.change_given),
            "payment_reference": sale.payment_reference or "",
            "payment_method": sale.payment_method,
            "payment_status": sale.payment_status,
        }


class SaleService:
    """Quick Sell posting and same-invoice revise."""

    def _settings(self) -> ApplicationSettings:
        row = ApplicationSettings.objects.filter(singleton_key=1).first()
        if row is None:
            return ApplicationSettings(enforce_safe_selling_price=False)
        return row

    def _payment_status(self, grand: Decimal, paid: Decimal, method: str) -> str:
        if paid <= 0:
            return "CREDIT" if method == "CREDIT" else "UNPAID"
        if paid < grand:
            return "PARTIAL"
        return "PAID"

    def _resolve_payment_amounts(self, payload: dict, grand_total: Decimal, payment_method: str) -> tuple[Decimal, Decimal, Decimal, str]:
        """
        Derive amount_paid, tendered, change, and optional payment reference.

        Cash: customer may hand over more than the bill; change is returned.
        UPI/CARD/BANK: optional transaction id; typically mark fully paid.
        """
        method = (payment_method or "CASH").upper()
        reference = str(payload.get("payment_reference") or "").strip()
        tendered = Decimal(str(payload.get("amount_tendered") or 0))
        paid_raw = payload.get("amount_paid")
        if method == "CREDIT":
            return Decimal("0"), Decimal("0"), Decimal("0"), reference
        if paid_raw is None or paid_raw == "":
            paid = grand_total
        else:
            paid = Decimal(str(paid_raw))
        paid = min(max(paid, Decimal("0")), grand_total)
        if method == "CASH":
            if tendered <= 0 and paid > 0:
                tendered = paid
            change = max(Decimal("0"), (tendered - grand_total).quantize(Decimal("0.01"))) if tendered > 0 else Decimal("0")
            # Full cash settlement uses bill total as paid; tender/change are for the drawer.
            if tendered >= grand_total and paid_raw is None:
                paid = grand_total
            return paid, tendered, change, reference
        # Electronic: no cash change; tendered mirrors paid when omitted.
        if tendered <= 0:
            tendered = paid
        return paid, tendered, Decimal("0"), reference

    def _prepare_lines(self, items: list, settings_row: ApplicationSettings) -> tuple[list, Decimal]:
        prepared = []
        header_discount = Decimal("0")
        for row in items:
            product = Product.objects.select_for_update().get(pk=row["product_id"])
            qty = Decimal(str(row["quantity"]))
            unit_price = Decimal(str(row.get("unit_price") or row.get("selling_price")))
            discount = Decimal(str(row.get("discount_amount") or 0))
            disc_pct = Decimal(str(row.get("discount_percent") or 0))
            if disc_pct and not discount:
                discount = (qty * unit_price * disc_pct / Decimal("100")).quantize(Decimal("0.01"))
            override = bool(row.get("below_safe_override"))
            batch_id = row.get("batch_id")
            if batch_id:
                allocations = inventory_service.allocate_batch(product, qty, int(batch_id))
            else:
                allocations = inventory_service.allocate_fifo(product, qty)
            first = True
            for batch, take in allocations:
                resulting = unit_price - (discount / qty) if qty else unit_price
                below = resulting < batch.safe_selling_price
                if below and not override:
                    if settings_row.enforce_safe_selling_price:
                        raise ValidationError(
                            {
                                "safe_price": (
                                    f"{product.sku} is below the safe selling price and selling is blocked."
                                )
                            }
                        )
                    raise ValidationError(
                        {
                            "code": "SAFE_PRICE_WARNING",
                            "message": (
                                f"{product.sku} is below the safe selling price of {batch.safe_selling_price}."
                            ),
                            "batch_cost": str(batch.purchase_cost),
                            "selling_price": str(batch.selling_price),
                            "safe_selling_price": str(batch.safe_selling_price),
                            "requested_discount": str(discount),
                            "resulting_price": str(resulting.quantize(Decimal("0.01"))),
                            "margin": str((resulting - batch.purchase_cost).quantize(Decimal("0.01"))),
                            "product_id": product.id,
                        }
                    )
                line_discount = discount if first else Decimal("0")
                first = False
                prepared.append((product, batch, take, unit_price, line_discount, disc_pct, override, below))
                header_discount += line_discount
        return prepared, header_discount

    def _write_items(self, sale: Sale, prepared: list, header_discount: Decimal) -> None:
        subtotal = Decimal("0")
        gst_total = Decimal("0")
        for product, batch, take, unit_price, discount, disc_pct, override, below in prepared:
            line_net = (take * unit_price) - discount
            gst = (line_net * product.gst_rate / Decimal("100")).quantize(Decimal("0.01"))
            inventory_service.apply_movement(
                batch=batch,
                movement_type=StockMovementType.SALE,
                quantity_delta=-take,
                notes=sale.invoice_number,
                reference_type="sale",
                reference_id=str(sale.id),
            )
            if override and below:
                audit_service.record(
                    action="safe_price_override",
                    entity="sale",
                    entity_id=sale.id,
                    new_data={"sku": product.sku, "unit_price": str(unit_price)},
                )
            resulting = (line_net / take) if take else unit_price
            SaleItem.objects.create(
                sale=sale,
                product=product,
                batch=batch,
                quantity=take,
                unit_price=unit_price,
                discount_percent=disc_pct,
                discount_amount=discount,
                resulting_price=resulting.quantize(Decimal("0.01")),
                gst_rate=product.gst_rate,
                gst_amount=gst,
                line_total=line_net + gst,
                batch_cost=batch.purchase_cost,
                below_safe_price=below,
                below_safe_override=override,
            )
            subtotal += take * unit_price
            gst_total += gst
        sale.subtotal = subtotal
        sale.discount_amount = header_discount
        sale.taxable_amount = subtotal - header_discount
        sale.gst_amount = gst_total
        sale.grand_total = sale.taxable_amount + gst_total

    def _post_customer_ledger(self, sale: Sale, payment_method: str, payment_reference: str) -> None:
        if sale.customer_id is None:
            return
        ledger_service.post(
            party_type=PartyType.CUSTOMER,
            party_id=sale.customer_id,
            entry_type=LedgerEntryType.SALE,
            debit=sale.grand_total,
            reference_type="sale",
            reference_id=sale.id,
            notes=sale.invoice_number,
            entry_date=sale.invoice_date,
        )
        if sale.amount_paid > 0:
            payment_service.create_payment(
                {
                    "party_type": PartyType.CUSTOMER,
                    "party_id": sale.customer_id,
                    "amount": sale.amount_paid,
                    "method": payment_method if payment_method != "CREDIT" else "CASH",
                    "reference": payment_reference or sale.invoice_number,
                    "notes": f"Sale {sale.invoice_number}",
                    "payment_date": sale.invoice_date,
                }
            )

    def _unwind_sale(self, sale: Sale) -> None:
        """Put stock back and reverse customer ledger effects so the sale can be rebuilt."""
        if sale.returns.exists():
            raise ValidationError({"detail": "This invoice has returns and cannot be edited."})
        if sale.is_cancelled:
            raise ValidationError({"detail": "Cancelled sales cannot be edited."})
        for item in sale.items.select_related("batch"):
            inventory_service.apply_movement(
                batch=item.batch,
                movement_type=StockMovementType.SALE_RETURN,
                quantity_delta=item.quantity,
                notes=f"Revise {sale.invoice_number}",
                reference_type="sale_revise",
                reference_id=str(sale.id),
            )
        if sale.customer_id:
            if sale.grand_total > 0:
                ledger_service.post(
                    party_type=PartyType.CUSTOMER,
                    party_id=sale.customer_id,
                    entry_type=LedgerEntryType.ADJUSTMENT,
                    credit=sale.grand_total,
                    reference_type="sale_revise",
                    reference_id=sale.id,
                    notes=f"Void sale {sale.invoice_number}",
                    entry_date=sale.invoice_date,
                )
            if sale.amount_paid > 0:
                ledger_service.post(
                    party_type=PartyType.CUSTOMER,
                    party_id=sale.customer_id,
                    entry_type=LedgerEntryType.ADJUSTMENT,
                    debit=sale.amount_paid,
                    reference_type="sale_revise",
                    reference_id=sale.id,
                    notes=f"Void payment {sale.invoice_number}",
                    entry_date=sale.invoice_date,
                )
                # Soft-void matching receipt rows so history stays append-friendly.
                Payment.objects.filter(
                    party_type=PartyType.CUSTOMER,
                    party_id=sale.customer_id,
                    reference__in=list(filter(None, [sale.invoice_number, sale.payment_reference])),
                    amount=sale.amount_paid,
                ).update(notes=f"Superseded by revise of {sale.invoice_number}")
        sale.items.all().delete()

    def create_sale(self, payload: dict) -> Sale:
        items = payload.get("items") or []
        if not items:
            raise ValidationError({"items": "At least one item is required."})
        settings_row = self._settings()
        customer = None
        if payload.get("customer_id"):
            customer = Customer.objects.get(pk=payload["customer_id"])
        payment_method = (payload.get("payment_method") or "CASH").upper()
        if payment_method == "CREDIT" and customer is None:
            raise ValidationError({"customer_id": "Credit sales require a customer."})

        with transaction.atomic():
            prepared, header_discount = self._prepare_lines(items, settings_row)
            sale = Sale.objects.create(
                customer=customer,
                invoice_number=document_number_service.next_number("SALE"),
                invoice_date=payload.get("invoice_date") or timezone.localdate(),
                payment_method=payment_method,
                notes=payload.get("notes", ""),
            )
            self._write_items(sale, prepared, header_discount)
            paid, tendered, change, reference = self._resolve_payment_amounts(
                payload, sale.grand_total, payment_method
            )
            sale.amount_paid = paid
            sale.amount_tendered = tendered
            sale.change_given = change
            sale.payment_reference = reference
            sale.payment_status = self._payment_status(sale.grand_total, sale.amount_paid, payment_method)
            sale.save()
            self._post_customer_ledger(sale, payment_method, reference)
            return sale

    def revise_sale(self, sale: Sale, payload: dict) -> Sale:
        """Replace line items and payment on an existing invoice number."""
        items = payload.get("items") or []
        if not items:
            raise ValidationError({"items": "At least one item is required."})
        settings_row = self._settings()
        customer = None
        if payload.get("customer_id"):
            customer = Customer.objects.get(pk=payload["customer_id"])
        elif "customer_id" not in payload:
            customer = sale.customer
        payment_method = (payload.get("payment_method") or sale.payment_method or "CASH").upper()
        if payment_method == "CREDIT" and customer is None:
            raise ValidationError({"customer_id": "Credit sales require a customer."})

        with transaction.atomic():
            locked = Sale.objects.select_for_update().get(pk=sale.pk)
            self._unwind_sale(locked)
            prepared, header_discount = self._prepare_lines(items, settings_row)
            locked.customer = customer
            locked.payment_method = payment_method
            locked.notes = payload.get("notes", locked.notes)
            if payload.get("invoice_date"):
                locked.invoice_date = payload["invoice_date"]
            locked.save()
            self._write_items(locked, prepared, header_discount)
            paid, tendered, change, reference = self._resolve_payment_amounts(
                payload, locked.grand_total, payment_method
            )
            locked.amount_paid = paid
            locked.amount_tendered = tendered
            locked.change_given = change
            locked.payment_reference = reference
            locked.payment_status = self._payment_status(locked.grand_total, locked.amount_paid, payment_method)
            locked.save()
            self._post_customer_ledger(locked, payment_method, reference)
            audit_service.record(
                action="sale_revise",
                entity="sale",
                entity_id=locked.id,
                new_data={"invoice_number": locked.invoice_number, "grand_total": str(locked.grand_total)},
            )
            return locked

    def create_return(self, sale: Sale, items: list[dict], notes: str = "") -> SaleReturn:
        with transaction.atomic():
            ret = SaleReturn.objects.create(
                sale=sale,
                return_number=document_number_service.next_number("SALE_RETURN"),
                return_date=timezone.localdate(),
                notes=notes,
            )
            total = Decimal("0")
            for row in items:
                original = sale.items.select_related("product", "batch").get(pk=row["sale_item_id"])
                qty = Decimal(str(row["quantity"]))
                if qty <= 0 or qty > original.quantity:
                    raise ValidationError({"quantity": "Cannot return more than sold."})
                inventory_service.apply_movement(
                    batch=original.batch,
                    movement_type=StockMovementType.SALE_RETURN,
                    quantity_delta=qty,
                    notes=ret.return_number,
                    reference_type="sale_return",
                    reference_id=str(ret.id),
                )
                line = (qty * original.resulting_price).quantize(Decimal("0.01"))
                SaleReturnItem.objects.create(
                    sale_return=ret,
                    sale_item=original,
                    quantity=qty,
                    line_total=line,
                )
                total += line
            ret.grand_total = total
            ret.save()
            if sale.customer_id:
                ledger_service.post(
                    party_type=PartyType.CUSTOMER,
                    party_id=sale.customer_id,
                    entry_type=LedgerEntryType.SALE_RETURN,
                    credit=total,
                    reference_type="sale_return",
                    reference_id=ret.id,
                    notes=ret.return_number,
                )
            return ret


sale_service = SaleService()
invoice_payload_service = InvoicePayloadService()
