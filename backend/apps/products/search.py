"""
Smart Product Finder: tokenised server-side search that never dumps the catalog.

Each query token must match at least one indexed field. Results are annotated
with live stock and the active (newest open) batch.
"""

from __future__ import annotations

from decimal import Decimal

from django.db.models import DecimalField, F, OuterRef, Q, QuerySet, Subquery, Sum
from django.db.models.functions import Coalesce

from apps.inventory.models import InventoryBatch
from apps.products.models import Product


class ProductSearchService:
    """Backend search for the desktop finder. The browser never loads all SKUs."""

    TOKEN_FIELDS = (
        "name",
        "sku",
        "barcode",
        "model",
        "specification",
        "hsn_code",
        "storage_location",
        "brand__name",
        "category__name",
        "subcategory__name",
        "aliases__term",
        "tags__name",
        "vendor_links__vendor_sku",
        "vendor_links__vendor__name",
    )

    def search(
        self,
        query: str,
        *,
        category_id: int | None = None,
        brand_id: int | None = None,
        vendor_id: int | None = None,
        is_active: bool | None = True,
        stock_status: str | None = None,
        min_selling_price: Decimal | None = None,
        max_selling_price: Decimal | None = None,
    ) -> QuerySet[Product]:
        qs = Product.objects.select_related("category", "subcategory", "brand", "unit").prefetch_related(
            "aliases",
            "tags",
            "vendor_links__vendor",
        )
        if is_active is not None:
            qs = qs.filter(is_active=is_active)
        if category_id:
            qs = qs.filter(category_id=category_id)
        if brand_id:
            qs = qs.filter(brand_id=brand_id)
        if vendor_id:
            qs = qs.filter(vendor_links__vendor_id=vendor_id)
        tokens = list(filter(lambda part: bool(part), map(lambda raw: raw.strip(), query.split())))
        for token in tokens:
            token_query = Q()
            for field in self.TOKEN_FIELDS:
                token_query |= Q(**{f"{field}__icontains": token})
            qs = qs.filter(token_query)
        qs = qs.annotate(
            current_stock=Coalesce(
                Sum("batches__remaining_quantity"),
                Decimal("0"),
                output_field=DecimalField(max_digits=14, decimal_places=3),
            )
        )
        # Newest open lot (last prices entered) vs oldest lot with stock (what FIFO sells next).
        latest_batch = InventoryBatch.objects.filter(product_id=OuterRef("pk"), is_open=True).order_by(
            "-purchase_date",
            "-id",
        )
        fifo_batch = InventoryBatch.objects.filter(
            product_id=OuterRef("pk"),
            remaining_quantity__gt=0,
        ).order_by("purchase_date", "id")
        qs = qs.annotate(
            # Bill defaults: next lot that will leave the shelf (FIFO).
            active_batch_id=Subquery(fifo_batch.values("id")[:1]),
            active_cost=Subquery(fifo_batch.values("purchase_cost")[:1]),
            active_selling_price=Subquery(fifo_batch.values("selling_price")[:1]),
            active_safe_selling_price=Subquery(fifo_batch.values("safe_selling_price")[:1]),
            active_max_discount=Subquery(fifo_batch.values("maximum_discount_percent")[:1]),
            active_mrp=Subquery(fifo_batch.values("mrp")[:1]),
            next_lot_code=Subquery(fifo_batch.values("lot_code")[:1]),
            # Newest lot — for comparison when restocked at a different price.
            latest_batch_id=Subquery(latest_batch.values("id")[:1]),
            latest_selling_price=Subquery(latest_batch.values("selling_price")[:1]),
            latest_cost=Subquery(latest_batch.values("purchase_cost")[:1]),
            latest_mrp=Subquery(latest_batch.values("mrp")[:1]),
            latest_lot_code=Subquery(latest_batch.values("lot_code")[:1]),
        )
        if min_selling_price is not None:
            qs = qs.filter(active_selling_price__gte=min_selling_price)
        if max_selling_price is not None:
            qs = qs.filter(active_selling_price__lte=max_selling_price)
        if stock_status == "out_of_stock":
            qs = qs.filter(current_stock__lte=0)
        elif stock_status == "low_stock":
            qs = qs.filter(current_stock__gt=0, current_stock__lte=F("reorder_level"))
        elif stock_status == "in_stock":
            qs = qs.filter(current_stock__gt=0)
        return qs.distinct().order_by("name")


product_search_service = ProductSearchService()
product_search_service = product_search_service
