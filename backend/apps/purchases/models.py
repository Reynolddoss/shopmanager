"""
Purchase documents and line items that freeze pricing at the moment of buy.

Posting goes through PurchaseService: create header + items + new batches +
stock + optional payment + vendor ledger in one transaction.
"""

from __future__ import annotations

from django.core.validators import MinValueValidator
from django.db import models

from apps.core.models import TimeStampedModel


class Purchase(TimeStampedModel):
    """Supplier bill. Soft-cancel via is_cancelled; never hard-delete posted bills."""

    vendor = models.ForeignKey("vendors.Vendor", on_delete=models.PROTECT, related_name="purchases")
    bill_number = models.CharField(max_length=64, unique=True, db_index=True)
    bill_date = models.DateField(db_index=True)
    payment_terms = models.CharField(max_length=255, blank=True, default="")
    notes = models.TextField(blank=True, default="")
    subtotal = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    discount_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    taxable_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    gst_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    other_charges = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    grand_total = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    amount_paid = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    payment_method = models.CharField(max_length=16, blank=True, default="")
    is_cancelled = models.BooleanField(default=False)

    class Meta:
        ordering = ["-bill_date", "-id"]

    def __str__(self) -> str:
        return f"Purchase {self.bill_number}"


class PurchaseItem(TimeStampedModel):
    """One purchased SKU line. Historical prices stay frozen on this row and its batch."""

    purchase = models.ForeignKey(Purchase, on_delete=models.PROTECT, related_name="items")
    product = models.ForeignKey("products.Product", on_delete=models.PROTECT, related_name="purchase_items")
    batch = models.ForeignKey(
        "inventory.InventoryBatch",
        on_delete=models.PROTECT,
        related_name="purchase_items",
        null=True,
        blank=True,
    )
    quantity = models.DecimalField(max_digits=14, decimal_places=3, validators=[MinValueValidator(0)])
    base_purchase_price = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(0)])
    supplier_discount_percent = models.DecimalField(
        max_digits=5, decimal_places=2, default=0, validators=[MinValueValidator(0)]
    )
    supplier_discount_amount = models.DecimalField(
        max_digits=12, decimal_places=2, default=0, validators=[MinValueValidator(0)]
    )
    effective_purchase_cost = models.DecimalField(
        max_digits=12, decimal_places=2, validators=[MinValueValidator(0)]
    )
    mrp = models.DecimalField(max_digits=12, decimal_places=2, default=0, validators=[MinValueValidator(0)])
    selling_price = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(0)])
    safe_selling_price = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(0)])
    maximum_customer_discount_percent = models.DecimalField(
        max_digits=5, decimal_places=2, default=0, validators=[MinValueValidator(0)]
    )
    gst_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    gst_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    line_total = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    pricing_mode = models.CharField(max_length=16, default="NEW")
    notes = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["id"]

    def __str__(self) -> str:
        return f"PurchaseItem {self.pk} product={self.product_id}"


class PurchaseReturn(TimeStampedModel):
    """Return against a posted purchase. The original bill is never deleted."""

    purchase = models.ForeignKey(Purchase, on_delete=models.PROTECT, related_name="returns")
    return_number = models.CharField(max_length=64, unique=True)
    return_date = models.DateField(db_index=True)
    notes = models.TextField(blank=True, default="")
    grand_total = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    class Meta:
        ordering = ["-return_date", "-id"]


class PurchaseReturnItem(TimeStampedModel):
    purchase_return = models.ForeignKey(PurchaseReturn, on_delete=models.PROTECT, related_name="items")
    purchase_item = models.ForeignKey(PurchaseItem, on_delete=models.PROTECT, related_name="return_items")
    quantity = models.DecimalField(max_digits=14, decimal_places=3, validators=[MinValueValidator(0)])
    line_total = models.DecimalField(max_digits=14, decimal_places=2, default=0)
