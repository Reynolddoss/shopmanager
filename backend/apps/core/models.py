"""
Shared persistence: timestamps, application settings, and audit history.

Master data for products, vendors, and customers lives in domain apps.
This app owns cross-cutting records that every domain may write to.
"""

from __future__ import annotations

from django.db import models


class TimeStampedModel(models.Model):
    """
    Abstract base for created_at / updated_at.

    Important financial and master records must remain auditable. Subclasses
    never silently overwrite timestamps because Django auto_now handles updates.
    """

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class ApplicationSettings(TimeStampedModel):
    """
    Singleton row for shop-wide configuration.

    Invoice prefixes, GSTIN, backup preferences, and pricing defaults belong
    here so they are not duplicated across views or frontend constants.
    """

    singleton_key = models.PositiveSmallIntegerField(default=1, unique=True, editable=False)
    shop_name = models.CharField(max_length=255, default="")
    address = models.TextField(blank=True, default="")
    gstin = models.CharField(max_length=32, blank=True, default="")
    phone = models.CharField(max_length=32, blank=True, default="")
    invoice_prefix = models.CharField(max_length=16, default="SH")
    currency = models.CharField(max_length=8, default="INR")
    default_tax_inclusive = models.BooleanField(default=False)
    low_stock_threshold = models.PositiveIntegerField(default=5)
    backup_retention_count = models.PositiveIntegerField(default=14)
    scheduled_backup_enabled = models.BooleanField(default=False)
    extra = models.JSONField(
        default=dict,
        blank=True,
        help_text="Extensible bag for future pricing and notification settings.",
    )
    inventory_valuation_method = models.CharField(
        max_length=32,
        default="FIFO",
        help_text="FIFO is the Phase 2 default. Weighted average can be plugged in later.",
    )
    sale_invoice_prefix = models.CharField(max_length=16, default="SH")
    purchase_invoice_prefix = models.CharField(max_length=16, default="PUR")
    enforce_safe_selling_price = models.BooleanField(
        default=False,
        help_text="If true, sales below safe price are blocked. Phase 3 default is warn-and-override.",
    )
    ui_theme = models.CharField(
        max_length=32,
        default="midnight",
        help_text="Desktop UI theme id: midnight, slate, or paper.",
    )

    class Meta:
        verbose_name = "application settings"
        verbose_name_plural = "application settings"

    def __str__(self) -> str:
        return f"Settings for {self.shop_name}"


class AuditLog(models.Model):
    """
    Append-only audit trail for important business actions.

    Designed for a later multi-user desktop: actor is a string identifier now
    (system / local-owner) and can become a foreign key later without rewriting
    historical rows.
    """

    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    action = models.CharField(max_length=64, db_index=True)
    entity = models.CharField(max_length=64, db_index=True)
    entity_id = models.CharField(max_length=64, db_index=True)
    old_data = models.JSONField(null=True, blank=True)
    new_data = models.JSONField(null=True, blank=True)
    source = models.CharField(max_length=64, default="api")
    actor = models.CharField(max_length=128, default="system")

    class Meta:
        ordering = ["-timestamp"]
        indexes = [
            models.Index(fields=["entity", "entity_id"]),
        ]

    def __str__(self) -> str:
        return f"{self.timestamp} {self.action} {self.entity}:{self.entity_id}"


class ShopOperator(TimeStampedModel):
    """
    Local shop user linked to Django auth.User.

    Phase 1 desktop uses a single owner account created at registration. The
    model stays extensible for cashier / manager roles later.
    """

    user = models.OneToOneField("auth.User", on_delete=models.CASCADE, related_name="shop_operator")
    full_name = models.CharField(max_length=128)
    phone = models.CharField(max_length=32, blank=True, default="")
    is_owner = models.BooleanField(default=False, db_index=True)

    class Meta:
        ordering = ["full_name"]

    def __str__(self) -> str:
        return self.full_name


class DocumentSequence(models.Model):
    """
    Server-side document numbers. React never allocates invoice numbers.

    One row per document type + financial year. next_value is incremented
    inside select_for_update so two concurrent sales cannot share a number.
    """

    document_type = models.CharField(max_length=32, db_index=True)
    financial_year = models.CharField(max_length=9, db_index=True)
    prefix = models.CharField(max_length=16, default="MM")
    next_value = models.PositiveIntegerField(default=1)

    class Meta:
        unique_together = ("document_type", "financial_year")

    def __str__(self) -> str:
        return f"{self.document_type} {self.financial_year} -> {self.next_value}"
