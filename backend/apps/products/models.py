"""
Product catalog master data: categories, brands, units, products, aliases.

Products are generic electrical SKUs, not wire-only or fan-only schemas.
Vendors are never stored as a single FK on Product; ProductVendor is the link.
"""

from __future__ import annotations

import uuid
from pathlib import Path

from django.core.validators import MinValueValidator
from django.db import models

from apps.core.models import TimeStampedModel


def product_image_upload_to(instance: "Product", filename: str) -> str:
    """Store under products/<sku>_<random>.ext so upgrades never overwrite files."""
    safe_sku = "".join(ch for ch in (instance.sku or "product") if ch.isalnum() or ch in "-_")[:40] or "product"
    ext = Path(filename).suffix.lower()
    if ext not in {".jpg", ".jpeg", ".png", ".webp", ".gif"}:
        ext = ".jpg"
    return f"products/{safe_sku}_{uuid.uuid4().hex[:12]}{ext}"


class Category(TimeStampedModel):
    """Top-level grouping (wires, switches, lighting, protection, etc.)."""

    name = models.CharField(max_length=128, unique=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "categories"

    def __str__(self) -> str:
        return self.name


class Subcategory(TimeStampedModel):
    """Optional child of a category for finer browsing later."""

    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="subcategories")
    name = models.CharField(max_length=128)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        unique_together = ("category", "name")
        verbose_name_plural = "subcategories"

    def __str__(self) -> str:
        return f"{self.category.name} / {self.name}"


class Brand(TimeStampedModel):
    """Manufacturer or house brand (Polycab, Anchor, Crompton, ...)."""

    name = models.CharField(max_length=128, unique=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class Unit(TimeStampedModel):
    """Stocking unit: metre, piece, coil, box, kg, etc."""

    name = models.CharField(max_length=64, unique=True)
    abbreviation = models.CharField(max_length=16)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.abbreviation


class Product(TimeStampedModel):
    """
    Permanent catalog item.

    Pricing on this row is a default suggestion only. Actual sellable stock and
    historical purchase cost live on InventoryBatch so older lots are never
    overwritten when a new purchase arrives.
    """

    name = models.CharField(max_length=255, db_index=True)
    sku = models.CharField(max_length=64, unique=True)
    barcode = models.CharField(max_length=64, blank=True, default="", db_index=True)
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="products")
    subcategory = models.ForeignKey(
        Subcategory,
        on_delete=models.PROTECT,
        related_name="products",
        null=True,
        blank=True,
    )
    brand = models.ForeignKey(
        Brand,
        on_delete=models.PROTECT,
        related_name="products",
        null=True,
        blank=True,
    )
    model = models.CharField(max_length=128, blank=True, default="")
    specification = models.TextField(blank=True, default="")
    unit = models.ForeignKey(Unit, on_delete=models.PROTECT, related_name="products")
    hsn_code = models.CharField(max_length=16, blank=True, default="")
    gst_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0)],
    )
    mrp = models.DecimalField(max_digits=12, decimal_places=2, default=0, validators=[MinValueValidator(0)])
    default_selling_price = models.DecimalField(
        max_digits=12, decimal_places=2, default=0, validators=[MinValueValidator(0)]
    )
    default_safe_selling_price = models.DecimalField(
        max_digits=12, decimal_places=2, default=0, validators=[MinValueValidator(0)]
    )
    default_maximum_discount_percent = models.DecimalField(
        max_digits=5, decimal_places=2, default=0, validators=[MinValueValidator(0)]
    )
    is_active = models.BooleanField(default=True, db_index=True)
    storage_location = models.CharField(max_length=128, blank=True, default="")
    notes = models.TextField(blank=True, default="")
    min_stock_quantity = models.DecimalField(
        max_digits=14, decimal_places=3, default=0, validators=[MinValueValidator(0)]
    )
    max_stock_quantity = models.DecimalField(
        max_digits=14, decimal_places=3, default=0, validators=[MinValueValidator(0)]
    )
    reorder_level = models.DecimalField(
        max_digits=14, decimal_places=3, default=0, validators=[MinValueValidator(0)]
    )
    # Optional catalog photo — shown on the product card and inventory list.
    image = models.ImageField(upload_to=product_image_upload_to, blank=True, null=True)
    vendors = models.ManyToManyField(
        "vendors.Vendor",
        through="products.ProductVendor",
        related_name="catalog_products",
        blank=True,
    )
    tags = models.ManyToManyField("products.Tag", related_name="products", blank=True)

    class Meta:
        ordering = ["name"]
        indexes = [
            models.Index(fields=["name", "sku"]),
            models.Index(fields=["barcode"]),
            models.Index(fields=["hsn_code"]),
            models.Index(fields=["is_active", "category"]),
        ]

    def __str__(self) -> str:
        return f"{self.sku} {self.name}"


class Tag(TimeStampedModel):
    """Searchable label (house-wire, 2.5sqmm, lighting) independent of category."""

    name = models.CharField(max_length=64, unique=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class ProductAlias(TimeStampedModel):
    """
    Search terms for the future Smart Product Finder.

    Example: product "Polycab 2.5 sq mm FR House Wire" may have aliases
    "2.5 wire", "2.5mm wire", "house wire".
    """

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="aliases")
    term = models.CharField(max_length=128, db_index=True)

    class Meta:
        unique_together = ("product", "term")
        verbose_name_plural = "product aliases"

    def __str__(self) -> str:
        return self.term


class ProductVendor(TimeStampedModel):
    """
    Many-to-many commercial relationship between a product and a vendor.

    Price snapshots here are convenience caches (last / average / lowest).
    PurchaseItem and InventoryBatch remain the authoritative history and must
    not be duplicated as a full ledger on this row.
    """

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="vendor_links")
    vendor = models.ForeignKey("vendors.Vendor", on_delete=models.PROTECT, related_name="product_links")
    vendor_sku = models.CharField(max_length=64, blank=True, default="")
    is_preferred = models.BooleanField(default=False)
    last_purchase_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    average_purchase_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    lowest_historical_purchase_price = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True
    )
    last_purchase_date = models.DateField(null=True, blank=True)
    typical_discount_percent = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    lead_time_days = models.PositiveIntegerField(null=True, blank=True)
    minimum_order_quantity = models.DecimalField(max_digits=12, decimal_places=3, null=True, blank=True)
    notes = models.TextField(blank=True, default="")

    class Meta:
        unique_together = ("product", "vendor")

    def __str__(self) -> str:
        return f"{self.product.sku} ← {self.vendor.name}"
