"""Sale and invoice serializers. Posting goes through SaleService."""

from __future__ import annotations

from rest_framework import serializers

from apps.sales.models import Sale, SaleItem, SaleReturn, SaleReturnItem


class SaleItemSerializer(serializers.ModelSerializer):
    sku = serializers.CharField(source="product.sku", read_only=True)
    product_name = serializers.CharField(source="product.name", read_only=True)
    specification = serializers.CharField(source="product.specification", read_only=True)

    class Meta:
        model = SaleItem
        fields = (
            "id",
            "product",
            "sku",
            "product_name",
            "specification",
            "batch",
            "quantity",
            "unit_price",
            "discount_percent",
            "discount_amount",
            "resulting_price",
            "gst_rate",
            "gst_amount",
            "line_total",
            "batch_cost",
            "below_safe_price",
            "below_safe_override",
        )
        read_only_fields = fields


class SaleListSerializer(serializers.ModelSerializer):
    """Compact row for history browse (no nested line items)."""

    customer_name = serializers.CharField(source="customer.name", read_only=True, allow_null=True)
    amount_due = serializers.SerializerMethodField()
    item_count = serializers.SerializerMethodField()

    class Meta:
        model = Sale
        fields = (
            "id",
            "customer",
            "customer_name",
            "invoice_number",
            "invoice_date",
            "grand_total",
            "amount_paid",
            "amount_due",
            "amount_tendered",
            "change_given",
            "payment_reference",
            "payment_method",
            "payment_status",
            "is_cancelled",
            "item_count",
            "created_at",
        )
        read_only_fields = fields

    def get_amount_due(self, obj: Sale) -> str:
        return str(obj.grand_total - obj.amount_paid)

    def get_item_count(self, obj: Sale) -> int:
        return obj.items.count()


class SaleSerializer(serializers.ModelSerializer):
    items = SaleItemSerializer(many=True, read_only=True)
    customer_name = serializers.CharField(source="customer.name", read_only=True, allow_null=True)
    amount_due = serializers.SerializerMethodField()

    class Meta:
        model = Sale
        fields = (
            "id",
            "customer",
            "customer_name",
            "invoice_number",
            "invoice_date",
            "notes",
            "subtotal",
            "discount_amount",
            "taxable_amount",
            "gst_amount",
            "grand_total",
            "amount_paid",
            "amount_due",
            "amount_tendered",
            "change_given",
            "payment_reference",
            "payment_method",
            "payment_status",
            "is_cancelled",
            "items",
            "created_at",
        )
        read_only_fields = fields

    def get_amount_due(self, obj: Sale) -> str:
        return str(obj.grand_total - obj.amount_paid)


class SaleWriteSerializer(serializers.Serializer):
    customer_id = serializers.IntegerField(required=False, allow_null=True)
    invoice_date = serializers.DateField(required=False)
    payment_method = serializers.CharField(required=False)
    amount_paid = serializers.DecimalField(max_digits=14, decimal_places=2, required=False, allow_null=True)
    amount_tendered = serializers.DecimalField(max_digits=14, decimal_places=2, required=False)
    payment_reference = serializers.CharField(required=False, allow_blank=True)
    notes = serializers.CharField(required=False, allow_blank=True)
    items = serializers.ListField(child=serializers.DictField(), allow_empty=False)


class SaleReturnItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = SaleReturnItem
        fields = ("id", "sale_item", "quantity", "line_total")


class SaleReturnSerializer(serializers.ModelSerializer):
    items = SaleReturnItemSerializer(many=True, read_only=True)

    class Meta:
        model = SaleReturn
        fields = ("id", "sale", "return_number", "return_date", "notes", "grand_total", "items")
