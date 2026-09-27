"""Catalog endpoints. Business rules stay in ProductService and ProductSearchService."""

from __future__ import annotations

from decimal import Decimal

from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.request import Request
from rest_framework.response import Response

from apps.inventory.services import inventory_service
from apps.inventory.valuation import valuation_service
from apps.products.image_service import product_image_service
from apps.products.models import Brand, Category, Product, ProductVendor, Subcategory, Tag, Unit
from apps.products.search import product_search_service
from apps.products.serializers import (
    BrandSerializer,
    CategorySerializer,
    FinderResultSerializer,
    ProductSerializer,
    ProductVendorSerializer,
    SubcategorySerializer,
    TagSerializer,
    UnitSerializer,
)
from apps.products.services import product_service, sku_suggestion_service


class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    search_fields = ("name",)
    filterset_fields = ("is_active",)
    http_method_names = ["get", "post", "patch", "head", "options"]


class SubcategoryViewSet(viewsets.ModelViewSet):
    queryset = Subcategory.objects.select_related("category").all()
    serializer_class = SubcategorySerializer
    search_fields = ("name",)
    filterset_fields = ("category", "is_active")
    http_method_names = ["get", "post", "patch", "head", "options"]


class BrandViewSet(viewsets.ModelViewSet):
    queryset = Brand.objects.all()
    serializer_class = BrandSerializer
    search_fields = ("name",)
    filterset_fields = ("is_active",)
    http_method_names = ["get", "post", "patch", "head", "options"]


class UnitViewSet(viewsets.ModelViewSet):
    queryset = Unit.objects.all()
    serializer_class = UnitSerializer
    search_fields = ("name", "abbreviation")
    filterset_fields = ("is_active",)
    http_method_names = ["get", "post", "patch", "head", "options"]


class TagViewSet(viewsets.ModelViewSet):
    queryset = Tag.objects.all()
    serializer_class = TagSerializer
    search_fields = ("name",)
    filterset_fields = ("is_active",)
    http_method_names = ["get", "post", "patch", "head", "options"]


class ProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.select_related("category", "subcategory", "brand", "unit").prefetch_related(
        "aliases",
        "tags",
    )
    serializer_class = ProductSerializer
    search_fields = ("name", "sku", "barcode", "model", "aliases__term")
    filterset_fields = ("category", "brand", "is_active", "subcategory")
    http_method_names = ["get", "post", "patch", "head", "options", "delete"]
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def destroy(self, request: Request, *args, **kwargs) -> Response:
        # DELETE is reserved for /products/{id}/image/; catalog rows stay soft-deactivate via PATCH.
        return Response(
            {
                "error": {
                    "code": "method_not_allowed",
                    "message": "Deactivate a product with PATCH is_active=false instead of deleting.",
                    "details": None,
                }
            },
            status=405,
        )

    def perform_create(self, serializer: ProductSerializer) -> None:
        alias_terms = serializer.validated_data.pop("alias_terms", [])
        product = serializer.save()
        product_service.replace_aliases(product=product, alias_terms=alias_terms)

    def perform_update(self, serializer: ProductSerializer) -> None:
        alias_terms = serializer.validated_data.pop("alias_terms", None)
        product = serializer.save()
        if alias_terms is not None:
            product_service.replace_aliases(product=product, alias_terms=alias_terms)

    @action(
        detail=True,
        methods=["post", "delete"],
        url_path="image",
        parser_classes=[MultiPartParser, FormParser],
    )
    def image(self, request: Request, pk: str | None = None) -> Response:
        """Attach, replace, or clear the catalog photo for this product."""
        product = self.get_object()
        if request.method == "DELETE":
            product_image_service.clear(product)
            return Response(ProductSerializer(product).data)
        upload = request.FILES.get("image")
        if upload is None:
            return Response(
                {"error": {"code": "bad_request", "message": "Choose a picture to upload.", "details": None}},
                status=400,
            )
        product_image_service.assign(product, upload)
        return Response(ProductSerializer(product).data)

    @action(detail=False, methods=["get"], url_path="suggest-sku")
    def suggest_sku(self, request: Request) -> Response:
        """Suggest a unique SKU from product name initials + next serial (e.g. CP-00012)."""
        name = (request.query_params.get("name") or "").strip()
        if not name:
            return Response({"error": {"code": "bad_request", "message": "name is required.", "details": None}}, status=400)
        return Response(sku_suggestion_service.suggest(name))

    @action(detail=False, methods=["get"], url_path="finder")
    def finder(self, request: Request) -> Response:
        """Smart Product Finder: token search plus live stock and active-batch prices."""
        query = request.query_params.get("q", "")
        category = request.query_params.get("category")
        brand = request.query_params.get("brand")
        vendor = request.query_params.get("vendor")
        stock_status = request.query_params.get("stock_status")
        min_price = request.query_params.get("min_price")
        max_price = request.query_params.get("max_price")
        qs = product_search_service.search(
            query,
            category_id=int(category) if category else None,
            brand_id=int(brand) if brand else None,
            vendor_id=int(vendor) if vendor else None,
            stock_status=stock_status or None,
            min_selling_price=Decimal(min_price) if min_price else None,
            max_selling_price=Decimal(max_price) if max_price else None,
        )
        page = self.paginate_queryset(qs)
        rows = list(map(lambda product: self._finder_row(product), page or list(qs[:50])))
        if page is not None:
            return self.get_paginated_response(FinderResultSerializer(rows, many=True).data)
        return Response(FinderResultSerializer(rows, many=True).data)

    @action(detail=True, methods=["get"], url_path="open-lots")
    def open_lots(self, request: Request, pk: str | None = None) -> Response:
        """Lots with remaining stock for counter lot-picking (FIFO order)."""
        product = self.get_object()
        return Response(inventory_service.open_lots_for_billing(product))

    def _finder_row(self, product: Product) -> dict:
        preferred = product.vendor_links.filter(is_preferred=True).select_related("vendor").first()
        cheapest = product.vendor_links.order_by("lowest_historical_purchase_price").first()
        last = product.vendor_links.order_by("-last_purchase_date").first()
        on_hand = getattr(product, "current_stock", Decimal("0")) or Decimal("0")
        return {
            "id": product.pk,
            "name": product.name,
            "sku": product.sku,
            "barcode": product.barcode,
            "specification": product.specification,
            "brand_name": product.brand.name if product.brand_id else "",
            "category_name": product.category.name,
            "current_stock": on_hand,
            "stock_status": inventory_service.stock_status(product, on_hand),
            "active_batch_id": getattr(product, "active_batch_id", None),
            "active_cost": getattr(product, "active_cost", None),
            "active_selling_price": getattr(product, "active_selling_price", None),
            "active_safe_selling_price": getattr(product, "active_safe_selling_price", None),
            "active_max_discount": getattr(product, "active_max_discount", None),
            "active_mrp": getattr(product, "active_mrp", None),
            "next_lot_code": getattr(product, "next_lot_code", None),
            "latest_batch_id": getattr(product, "latest_batch_id", None),
            "latest_selling_price": getattr(product, "latest_selling_price", None),
            "latest_cost": getattr(product, "latest_cost", None),
            "latest_mrp": getattr(product, "latest_mrp", None),
            "latest_lot_code": getattr(product, "latest_lot_code", None),
            "image_url": product.image.url if product.image else None,
            "preferred_vendor": preferred.vendor.name if preferred else None,
            "last_purchase_price": last.last_purchase_price if last else None,
            "lowest_historical_purchase_price": cheapest.lowest_historical_purchase_price if cheapest else None,
        }

    @action(detail=True, methods=["get"], url_path="card")
    def card(self, request: Request, pk: str | None = None) -> Response:
        """Premium product card: overview, stock, pricing, vendors, batch history."""
        product = self.get_object()
        # Newest first for display; FIFO next = oldest with remaining qty.
        batches = list(product.batches.order_by("-purchase_date", "-id"))
        on_hand = sum(map(lambda batch: batch.remaining_quantity, batches), Decimal("0"))
        latest = next(filter(lambda batch: batch.is_open and batch.remaining_quantity > 0, batches), None)
        fifo_ordered = sorted(
            filter(lambda batch: batch.remaining_quantity > 0, batches),
            key=lambda batch: (str(batch.purchase_date or ""), batch.id),
        )
        next_lot = fifo_ordered[0] if fifo_ordered else None

        def _pricing(batch):
            if batch is None:
                return None
            return {
                "lot_code": batch.lot_code,
                "mrp": str(batch.mrp),
                "selling_price": str(batch.selling_price),
                "safe_selling_price": str(batch.safe_selling_price),
                "maximum_discount_percent": str(batch.maximum_discount_percent),
                "current_cost": str(batch.purchase_cost),
                **inventory_service.margin_snapshot(
                    cost=batch.purchase_cost,
                    selling=batch.selling_price,
                    safe=batch.safe_selling_price,
                    max_discount=batch.maximum_discount_percent,
                ),
            }

        return Response(
            {
                "product": ProductSerializer(product).data,
                "stock": {
                    "on_hand": str(on_hand),
                    "status": inventory_service.stock_status(product, on_hand),
                    "min_stock_quantity": str(product.min_stock_quantity),
                    "max_stock_quantity": str(product.max_stock_quantity),
                    "reorder_level": str(product.reorder_level),
                    "valuation_method": "FIFO",
                    "on_hand_value": str(valuation_service.value_on_hand(product, method="FIFO")),
                },
                # Default counter/overview price = next lot sold (FIFO).
                "pricing": _pricing(next_lot),
                "pricing_latest": _pricing(latest) if latest and next_lot and latest.id != next_lot.id else None,
                "vendors": ProductVendorSerializer(product.vendor_links.select_related("vendor"), many=True).data,
                "batches": list(
                    map(
                        lambda batch: {
                            "id": batch.pk,
                            "lot_code": batch.lot_code,
                            "vendor_name": batch.vendor.name if batch.vendor_id else "",
                            "purchase_date": batch.purchase_date,
                            "purchase_cost": str(batch.purchase_cost),
                            "selling_price": str(batch.selling_price),
                            "safe_selling_price": str(batch.safe_selling_price),
                            "maximum_discount_percent": str(batch.maximum_discount_percent),
                            "remaining_quantity": str(batch.remaining_quantity),
                            "original_quantity": str(batch.original_quantity),
                        },
                        batches,
                    )
                ),
            }
        )


class ProductVendorViewSet(viewsets.ModelViewSet):
    queryset = ProductVendor.objects.select_related("product", "vendor").all()
    serializer_class = ProductVendorSerializer
    filterset_fields = ("product", "vendor", "is_preferred")
    http_method_names = ["get", "post", "patch", "head", "options"]
