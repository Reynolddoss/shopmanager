"""DRF serializers for catalog master data and Smart Finder rows."""

from __future__ import annotations

from rest_framework import serializers

from apps.products.models import Brand, Category, Product, ProductAlias, ProductVendor, Subcategory, Tag, Unit


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ("id", "name", "is_active", "created_at", "updated_at")
        read_only_fields = ("id", "created_at", "updated_at")


class SubcategorySerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source="category.name", read_only=True)

    class Meta:
        model = Subcategory
        fields = ("id", "category", "category_name", "name", "is_active", "created_at", "updated_at")
        read_only_fields = ("id", "category_name", "created_at", "updated_at")


class BrandSerializer(serializers.ModelSerializer):
    class Meta:
        model = Brand
        fields = ("id", "name", "is_active", "created_at", "updated_at")
        read_only_fields = ("id", "created_at", "updated_at")


class UnitSerializer(serializers.ModelSerializer):
    class Meta:
        model = Unit
        fields = ("id", "name", "abbreviation", "is_active", "created_at", "updated_at")
        read_only_fields = ("id", "created_at", "updated_at")


class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = ("id", "name", "is_active", "created_at", "updated_at")
        read_only_fields = ("id", "created_at", "updated_at")


class ProductAliasSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductAlias
        fields = ("id", "term", "created_at")
        read_only_fields = ("id", "created_at")


class ProductVendorSerializer(serializers.ModelSerializer):
    vendor_name = serializers.CharField(source="vendor.name", read_only=True)

    class Meta:
        model = ProductVendor
        fields = (
            "id",
            "product",
            "vendor",
            "vendor_name",
            "vendor_sku",
            "is_preferred",
            "last_purchase_price",
            "average_purchase_price",
            "lowest_historical_purchase_price",
            "last_purchase_date",
            "typical_discount_percent",
            "lead_time_days",
            "minimum_order_quantity",
            "notes",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at", "vendor_name")


class ProductSerializer(serializers.ModelSerializer):
    aliases = ProductAliasSerializer(many=True, read_only=True)
    tags = TagSerializer(many=True, read_only=True)
    tag_ids = serializers.PrimaryKeyRelatedField(
        many=True, queryset=Tag.objects.all(), write_only=True, required=False, source="tags"
    )
    alias_terms = serializers.ListField(child=serializers.CharField(), write_only=True, required=False)
    category_name = serializers.CharField(source="category.name", read_only=True)
    brand_name = serializers.CharField(source="brand.name", read_only=True, default="")
    unit_abbreviation = serializers.CharField(source="unit.abbreviation", read_only=True)
    # Browser-reachable path via Vite/Django /media proxy (null when no photo).
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = (
            "id",
            "name",
            "sku",
            "barcode",
            "category",
            "category_name",
            "subcategory",
            "brand",
            "brand_name",
            "model",
            "specification",
            "unit",
            "unit_abbreviation",
            "hsn_code",
            "gst_rate",
            "mrp",
            "default_selling_price",
            "default_safe_selling_price",
            "default_maximum_discount_percent",
            "is_active",
            "storage_location",
            "notes",
            "min_stock_quantity",
            "max_stock_quantity",
            "reorder_level",
            "image",
            "image_url",
            "aliases",
            "alias_terms",
            "tags",
            "tag_ids",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at", "aliases", "tags", "image_url")
        extra_kwargs = {"image": {"write_only": True, "required": False}}

    def get_image_url(self, obj: Product) -> str | None:
        if not obj.image:
            return None
        try:
            return obj.image.url
        except ValueError:
            return None


class FinderResultSerializer(serializers.Serializer):
    """
    Smart Finder row.

    active_* = next FIFO lot (default bill price). latest_* = newest lot when restocked.
    """

    id = serializers.IntegerField()
    name = serializers.CharField()
    sku = serializers.CharField()
    barcode = serializers.CharField()
    specification = serializers.CharField()
    brand_name = serializers.CharField()
    category_name = serializers.CharField()
    current_stock = serializers.DecimalField(max_digits=14, decimal_places=3)
    stock_status = serializers.CharField()
    active_batch_id = serializers.IntegerField(allow_null=True)
    active_cost = serializers.DecimalField(max_digits=12, decimal_places=2, allow_null=True)
    active_selling_price = serializers.DecimalField(max_digits=12, decimal_places=2, allow_null=True)
    active_safe_selling_price = serializers.DecimalField(max_digits=12, decimal_places=2, allow_null=True)
    active_max_discount = serializers.DecimalField(max_digits=5, decimal_places=2, allow_null=True)
    active_mrp = serializers.DecimalField(max_digits=12, decimal_places=2, allow_null=True)
    next_lot_code = serializers.CharField(allow_null=True, allow_blank=True)
    latest_batch_id = serializers.IntegerField(allow_null=True)
    latest_selling_price = serializers.DecimalField(max_digits=12, decimal_places=2, allow_null=True)
    latest_cost = serializers.DecimalField(max_digits=12, decimal_places=2, allow_null=True)
    latest_mrp = serializers.DecimalField(max_digits=12, decimal_places=2, allow_null=True)
    latest_lot_code = serializers.CharField(allow_null=True, allow_blank=True)
    image_url = serializers.CharField(allow_null=True, required=False)
    preferred_vendor = serializers.CharField(allow_null=True)
    last_purchase_price = serializers.DecimalField(max_digits=12, decimal_places=2, allow_null=True)
    lowest_historical_purchase_price = serializers.DecimalField(max_digits=12, decimal_places=2, allow_null=True)


FinderResultSerializer = FinderResultSerializer
