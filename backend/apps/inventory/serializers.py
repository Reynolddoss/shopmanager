"""Serializers for inventory batches, movements, and owner-confirmed batch entry."""

from __future__ import annotations

from rest_framework import serializers

from apps.inventory.models import InventoryBatch, StockMovement


class InventoryBatchSerializer(serializers.ModelSerializer):
    vendor_name = serializers.CharField(source="vendor.name", read_only=True)
    product_name = serializers.CharField(source="product.name", read_only=True)
    product_sku = serializers.CharField(source="product.sku", read_only=True)

    class Meta:
        model = InventoryBatch
        fields = (
            "id",
            "product",
            "product_name",
            "product_sku",
            "vendor",
            "vendor_name",
            "lot_code",
            "purchase_date",
            "invoice_reference",
            "list_purchase_price",
            "supplier_discount_percent",
            "supplier_discount_amount",
            "purchase_cost",
            "mrp",
            "selling_price",
            "safe_selling_price",
            "maximum_discount_percent",
            "bulk_price",
            "remaining_quantity",
            "original_quantity",
            "is_open",
            "pricing_mode",
            "pricing_confirmed",
            "notes",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "created_at",
            "updated_at",
            "purchase_cost",
            "vendor_name",
            "product_name",
            "product_sku",
        )


class StockMovementSerializer(serializers.ModelSerializer):
    class Meta:
        model = StockMovement
        fields = (
            "id",
            "product",
            "batch",
            "movement_type",
            "quantity",
            "quantity_before",
            "quantity_after",
            "reason",
            "reference_type",
            "reference_id",
            "notes",
            "created_at",
        )
        read_only_fields = ("id", "created_at")


class BatchCreateSerializer(serializers.Serializer):
    """Owner-facing batch entry. Pricing is never inferred on the server."""

    product = serializers.IntegerField()
    vendor = serializers.IntegerField(required=False, allow_null=True)
    quantity = serializers.DecimalField(max_digits=14, decimal_places=3)
    list_purchase_price = serializers.DecimalField(max_digits=12, decimal_places=2)
    supplier_discount_percent = serializers.DecimalField(max_digits=5, decimal_places=2, required=False, default=0)
    supplier_discount_amount = serializers.DecimalField(max_digits=12, decimal_places=2, required=False, default=0)
    purchase_date = serializers.DateField(required=False, allow_null=True)
    invoice_reference = serializers.CharField(required=False, allow_blank=True, default="")
    lot_code = serializers.CharField(required=False, allow_blank=True, default="")
    pricing_mode = serializers.ChoiceField(choices=["NEW", "PREVIOUS", "COPY_EDIT"], default="NEW")
    pricing_confirmed = serializers.BooleanField(default=False)
    selling_price = serializers.DecimalField(max_digits=12, decimal_places=2, required=False)
    safe_selling_price = serializers.DecimalField(max_digits=12, decimal_places=2, required=False)
    maximum_discount_percent = serializers.DecimalField(max_digits=5, decimal_places=2, required=False)
    mrp = serializers.DecimalField(max_digits=12, decimal_places=2, required=False)
    bulk_price = serializers.DecimalField(max_digits=12, decimal_places=2, required=False, allow_null=True)
    notes = serializers.CharField(required=False, allow_blank=True, default="")


class StockAdjustSerializer(serializers.Serializer):
    batch = serializers.IntegerField()
    movement_type = serializers.CharField()
    quantity = serializers.DecimalField(max_digits=14, decimal_places=3)
    reason = serializers.CharField(required=False, allow_blank=True, default="")
    notes = serializers.CharField(required=False, allow_blank=True, default="")
