"""
Batch-aware inventory and append-only stock movements.

The same SKU can exist in multiple purchase lots with different costs and
selling prices. Remaining quantity lives on the batch; movements explain every
change so stock never moves silently.
"""

from __future__ import annotations

from django.core.validators import MinValueValidator
from django.db import models

from apps.core.models import TimeStampedModel


class StockMovementType(models.TextChoices):
    """Extensible movement codes. New types can be added without rewriting rows."""

    OPENING_STOCK = "OPENING_STOCK", "Opening stock"
    PURCHASE = "PURCHASE", "Purchase"
    SALE = "SALE", "Sale"
    SALE_RETURN = "SALE_RETURN", "Sale return"
    PURCHASE_RETURN = "PURCHASE_RETURN", "Purchase return"
    ADJUSTMENT_IN = "ADJUSTMENT_IN", "Adjustment in"
    ADJUSTMENT_OUT = "ADJUSTMENT_OUT", "Adjustment out"
    DAMAGE = "DAMAGE", "Damage"
    EXPIRED = "EXPIRED", "Expired / unsellable"


class InventoryBatch(TimeStampedModel):
    """
    One purchase lot (or opening lot) for a product.

    Historical pricing on this row is a snapshot from when the lot was created.
    Later purchases create new batches instead of overwriting this one so
    previous-batch comparison remains possible.
    """

    product = models.ForeignKey("products.Product", on_delete=models.PROTECT, related_name="batches")
    vendor = models.ForeignKey(
        "vendors.Vendor",
        on_delete=models.PROTECT,
        related_name="batches",
        null=True,
        blank=True,
    )
    lot_code = models.CharField(max_length=64, db_index=True)
    purchase_date = models.DateField(null=True, blank=True, db_index=True)
    invoice_reference = models.CharField(max_length=64, blank=True, default="")
    list_purchase_price = models.DecimalField(
        max_digits=12, decimal_places=2, default=0, validators=[MinValueValidator(0)]
    )
    supplier_discount_percent = models.DecimalField(
        max_digits=5, decimal_places=2, default=0, validators=[MinValueValidator(0)]
    )
    supplier_discount_amount = models.DecimalField(
        max_digits=12, decimal_places=2, default=0, validators=[MinValueValidator(0)]
    )
    purchase_cost = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        help_text="Effective cost after supplier discount. Historical; never overwrite.",
    )
    mrp = models.DecimalField(max_digits=12, decimal_places=2, default=0, validators=[MinValueValidator(0)])
    selling_price = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(0)])
    safe_selling_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        help_text="Owner-approved floor. Software must not impose this automatically.",
    )
    maximum_discount_percent = models.DecimalField(
        max_digits=5, decimal_places=2, default=0, validators=[MinValueValidator(0)]
    )
    bulk_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    remaining_quantity = models.DecimalField(
        max_digits=14, decimal_places=3, validators=[MinValueValidator(0)]
    )
    original_quantity = models.DecimalField(
        max_digits=14, decimal_places=3, validators=[MinValueValidator(0)]
    )
    is_open = models.BooleanField(default=True, db_index=True)
    pricing_mode = models.CharField(
        max_length=16,
        default="NEW",
        help_text="PREVIOUS, COPY_EDIT, or NEW. Owner must confirm before save.",
    )
    pricing_confirmed = models.BooleanField(default=False)
    notes = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["-purchase_date", "-id"]
        unique_together = ("product", "lot_code")
        verbose_name_plural = "inventory batches"
        indexes = [
            models.Index(fields=["product", "is_open"]),
        ]

    def __str__(self) -> str:
        return f"{self.product.sku} {self.lot_code}"


class StockMovement(TimeStampedModel):
    """
    Immutable explanation of a quantity change.

    Quantity is signed at the application layer (positive in, negative out).
    Services must write a movement in the same transaction as the batch update.
    """

    product = models.ForeignKey("products.Product", on_delete=models.PROTECT, related_name="movements")
    batch = models.ForeignKey(
        InventoryBatch,
        on_delete=models.PROTECT,
        related_name="movements",
        null=True,
        blank=True,
    )
    movement_type = models.CharField(max_length=32, choices=StockMovementType.choices, db_index=True)
    quantity = models.DecimalField(max_digits=14, decimal_places=3)
    quantity_before = models.DecimalField(max_digits=14, decimal_places=3, default=0)
    quantity_after = models.DecimalField(max_digits=14, decimal_places=3, default=0)
    reason = models.CharField(max_length=255, blank=True, default="")
    reference_type = models.CharField(max_length=64, blank=True, default="")
    reference_id = models.CharField(max_length=64, blank=True, default="")
    notes = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.movement_type} {self.quantity} {self.product_id}"
