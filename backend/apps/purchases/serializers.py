"""Purchase document serializers. Posting goes through PurchaseService."""

from __future__ import annotations

from rest_framework import serializers

from apps.purchases.models import Purchase, PurchaseItem, PurchaseReturn, PurchaseReturnItem


class PurchaseItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = PurchaseItem
        fields = (
            "id",
            "product",
            "batch",
            "quantity",
            "base_purchase_price",
            "supplier_discount_percent",
            "supplier_discount_amount",
            "effective_purchase_cost",
            "mrp",
            "selling_price",
            "safe_selling_price",
            "maximum_customer_discount_percent",
            "gst_rate",
            "gst_amount",
            "line_total",
            "pricing_mode",
            "notes",
        )
        read_only_fields = fields


class PurchaseListSerializer(serializers.ModelSerializer):
    """Compact purchase row for history browse."""

    vendor_name = serializers.CharField(source="vendor.name", read_only=True)
    item_count = serializers.SerializerMethodField()

    class Meta:
        model = Purchase
        fields = (
            "id",
            "vendor",
            "vendor_name",
            "bill_number",
            "bill_date",
            "grand_total",
            "amount_paid",
            "payment_method",
            "is_cancelled",
            "item_count",
            "created_at",
        )
        read_only_fields = fields

    def get_item_count(self, obj: Purchase) -> int:
        return obj.items.count()


class PurchaseSerializer(serializers.ModelSerializer):
    items = PurchaseItemSerializer(many=True, read_only=True)
    vendor_name = serializers.CharField(source="vendor.name", read_only=True)

    class Meta:
        model = Purchase
        fields = (
            "id",
            "vendor",
            "vendor_name",
            "bill_number",
            "bill_date",
            "payment_terms",
            "notes",
            "subtotal",
            "discount_amount",
            "taxable_amount",
            "gst_amount",
            "other_charges",
            "grand_total",
            "amount_paid",
            "payment_method",
            "is_cancelled",
            "items",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class PurchaseWriteSerializer(serializers.Serializer):
    vendor_id = serializers.IntegerField()
    bill_date = serializers.DateField(required=False)
    payment_terms = serializers.CharField(required=False, allow_blank=True)
    notes = serializers.CharField(required=False, allow_blank=True)
    vendor_invoice_number = serializers.CharField(required=False, allow_blank=True)
    discount_amount = serializers.DecimalField(max_digits=12, decimal_places=2, required=False)
    other_charges = serializers.DecimalField(max_digits=12, decimal_places=2, required=False)
    amount_paid = serializers.DecimalField(max_digits=14, decimal_places=2, required=False)
    payment_method = serializers.CharField(required=False, allow_blank=True)
    items = serializers.ListField(child=serializers.DictField(), allow_empty=False)


class PurchaseReturnItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = PurchaseReturnItem
        fields = ("id", "purchase_item", "quantity", "line_total")


class PurchaseReturnSerializer(serializers.ModelSerializer):
    items = PurchaseReturnItemSerializer(many=True, read_only=True)

    class Meta:
        model = PurchaseReturn
        fields = ("id", "purchase", "return_number", "return_date", "notes", "grand_total", "items")
