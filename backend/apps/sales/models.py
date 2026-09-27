"""
Sales documents. Stock is reduced only through InventoryService.apply_movement.
Invoice numbers come from DocumentNumberService, never from the React client.
"""

from __future__ import annotations

from django.core.validators import MinValueValidator
from django.db import models

from apps.core.models import TimeStampedModel


class Sale(TimeStampedModel):
    """Customer invoice. Soft-cancel / return docs; never hard-delete a posted sale."""

    customer = models.ForeignKey(
        "customers.Customer",
        on_delete=models.PROTECT,
        related_name="sales",
        null=True,
        blank=True,
    )
    invoice_number = models.CharField(max_length=64, unique=True, db_index=True)
    invoice_date = models.DateField(db_index=True)
    notes = models.TextField(blank=True, default="")
    subtotal = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    discount_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    taxable_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    gst_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    grand_total = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    amount_paid = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    # Cash handed over at the counter (may exceed grand_total); change_given is returned.
    amount_tendered = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    change_given = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    # Optional UPI / card / bank reference (transaction id).
    payment_reference = models.CharField(max_length=128, blank=True, default="")
    payment_method = models.CharField(max_length=16, default="CASH")
    payment_status = models.CharField(max_length=16, default="UNPAID")
    is_cancelled = models.BooleanField(default=False)

    class Meta:
        ordering = ["-invoice_date", "-id"]

    def __str__(self) -> str:
        return self.invoice_number


class SaleItem(TimeStampedModel):
    """One billed lot line. FIFO allocation may split one product across several items."""

    sale = models.ForeignKey(Sale, on_delete=models.PROTECT, related_name="items")
    product = models.ForeignKey("products.Product", on_delete=models.PROTECT, related_name="sale_items")
    batch = models.ForeignKey("inventory.InventoryBatch", on_delete=models.PROTECT, related_name="sale_items")
    quantity = models.DecimalField(max_digits=14, decimal_places=3, validators=[MinValueValidator(0)])
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(0)])
    discount_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    discount_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    resulting_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    gst_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    gst_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    line_total = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    batch_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    below_safe_price = models.BooleanField(default=False)
    below_safe_override = models.BooleanField(default=False)

    class Meta:
        ordering = ["id"]


class SaleReturn(TimeStampedModel):
    """Return against a posted sale. The original invoice stays in history."""

    sale = models.ForeignKey(Sale, on_delete=models.PROTECT, related_name="returns")
    return_number = models.CharField(max_length=64, unique=True)
    return_date = models.DateField(db_index=True)
    notes = models.TextField(blank=True, default="")
    grand_total = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    class Meta:
        ordering = ["-return_date", "-id"]


class SaleReturnItem(TimeStampedModel):
    sale_return = models.ForeignKey(SaleReturn, on_delete=models.PROTECT, related_name="items")
    sale_item = models.ForeignKey(SaleItem, on_delete=models.PROTECT, related_name="return_items")
    quantity = models.DecimalField(max_digits=14, decimal_places=3, validators=[MinValueValidator(0)])
    line_total = models.DecimalField(max_digits=14, decimal_places=2, default=0)
