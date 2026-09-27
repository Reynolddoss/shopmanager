"""Inventory HTTP API. Stock and pricing mutations go through InventoryService."""

from __future__ import annotations

from decimal import Decimal

from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.response import Response

from apps.inventory.models import InventoryBatch, StockMovement, StockMovementType
from apps.inventory.serializers import (
    BatchCreateSerializer,
    InventoryBatchSerializer,
    StockAdjustSerializer,
    StockMovementSerializer,
)
from apps.inventory.services import inventory_service
from apps.products.models import Product
from apps.vendors.models import Vendor


class InventoryBatchViewSet(viewsets.ModelViewSet):
    queryset = InventoryBatch.objects.select_related("product", "vendor").all()
    serializer_class = InventoryBatchSerializer
    filterset_fields = ("product", "vendor", "is_open")
    search_fields = ("lot_code", "product__name", "product__sku", "invoice_reference")
    http_method_names = ["get", "post", "patch", "head", "options"]

    @action(detail=False, methods=["get"], url_path="previous")
    def previous(self, request: Request) -> Response:
        """Return the latest prior batch and cost-delta banner for a product."""
        product_id = request.query_params.get("product")
        new_cost = request.query_params.get("new_cost")
        if not product_id:
            return Response(
                {"error": {"code": "bad_request", "message": "product is required.", "details": None}},
                status=400,
            )
        product = Product.objects.filter(pk=product_id).first()
        if product is None:
            return Response(
                {"error": {"code": "not_found", "message": "Product not found.", "details": None}},
                status=404,
            )
        cost = Decimal(new_cost) if new_cost else Decimal("0")
        return Response(inventory_service.compare_with_previous(product, cost))

    @action(detail=False, methods=["post"], url_path="receive")
    def receive(self, request: Request) -> Response:
        """Create a new lot. Never updates an existing batch."""
        serializer = BatchCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        product = Product.objects.filter(pk=data["product"]).first()
        if product is None:
            return Response(
                {"error": {"code": "not_found", "message": "Product not found.", "details": None}},
                status=404,
            )
        vendor = Vendor.objects.filter(pk=data.get("vendor")).first() if data.get("vendor") else None
        batch = inventory_service.create_batch(
            product=product,
            vendor=vendor,
            quantity=data["quantity"],
            list_purchase_price=data["list_purchase_price"],
            supplier_discount_percent=data.get("supplier_discount_percent") or Decimal("0"),
            supplier_discount_amount=data.get("supplier_discount_amount") or Decimal("0"),
            purchase_date=data.get("purchase_date"),
            invoice_reference=data.get("invoice_reference") or "",
            lot_code=data.get("lot_code") or "",
            pricing_mode=data.get("pricing_mode") or "NEW",
            pricing_confirmed=bool(data.get("pricing_confirmed")),
            selling_price=data.get("selling_price"),
            safe_selling_price=data.get("safe_selling_price"),
            maximum_discount_percent=data.get("maximum_discount_percent"),
            mrp=data.get("mrp"),
            bulk_price=data.get("bulk_price"),
            notes=data.get("notes") or "",
        )
        return Response(InventoryBatchSerializer(batch).data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["get"], url_path="preview-margin")
    def preview_margin(self, request: Request) -> Response:
        """Display-only margin maths before the owner saves a lot."""
        cost = Decimal(request.query_params.get("cost") or "0")
        selling = Decimal(request.query_params.get("selling") or "0")
        safe = Decimal(request.query_params.get("safe") or "0")
        discount = Decimal(request.query_params.get("max_discount") or "0")
        return Response(
            inventory_service.margin_snapshot(cost=cost, selling=selling, safe=safe, max_discount=discount)
        )


class StockMovementViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """Movements are created by services, not by ad-hoc DELETE from the UI."""

    queryset = StockMovement.objects.select_related("product", "batch").all()
    serializer_class = StockMovementSerializer
    filterset_fields = ("product", "batch", "movement_type")
    http_method_names = ["get", "post", "head", "options"]

    @action(detail=False, methods=["post"], url_path="adjust")
    def adjust(self, request: Request) -> Response:
        """Opening stock, adjustment in/out, or damage against a batch."""
        serializer = StockAdjustSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        batch = InventoryBatch.objects.filter(pk=data["batch"]).first()
        if batch is None:
            return Response(
                {"error": {"code": "not_found", "message": "Batch not found.", "details": None}},
                status=404,
            )
        movement_type = data["movement_type"]
        quantity = data["quantity"]
        inbound = movement_type in {
            StockMovementType.OPENING_STOCK,
            StockMovementType.ADJUSTMENT_IN,
            StockMovementType.PURCHASE,
            StockMovementType.SALE_RETURN,
        }
        delta = quantity if inbound else -abs(quantity)
        if movement_type in {StockMovementType.ADJUSTMENT_OUT, StockMovementType.DAMAGE, StockMovementType.EXPIRED}:
            delta = -abs(quantity)
        movement = inventory_service.apply_movement(
            batch=batch,
            movement_type=movement_type,
            quantity_delta=delta,
            reason=data.get("reason") or "",
            notes=data.get("notes") or "",
        )
        return Response(StockMovementSerializer(movement).data, status=status.HTTP_201_CREATED)
