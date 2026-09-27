"""
Query filters shared by every analytics endpoint.

All heavy work stays in SQL aggregations. The React app only sends filter
parameters and renders the numbers Django returns.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from django.db.models import QuerySet
from django.utils import timezone

from apps.purchases.models import Purchase, PurchaseItem
from apps.sales.models import Sale, SaleItem


def money(value) -> str:
    """Stable two-decimal string for JSON. Never round in the browser."""
    if value is None:
        return "0.00"
    return str(Decimal(str(value)).quantize(Decimal("0.01")))


def qty(value) -> str:
    if value is None:
        return "0.000"
    return str(Decimal(str(value)).quantize(Decimal("0.001")))


@dataclass
class AnalyticsFilters:
    """Parsed query-string filters for sales / purchases / expenses."""

    date_from: date | None
    date_to: date | None
    category_id: int | None
    brand_id: int | None
    vendor_id: int | None
    customer_id: int | None
    product_id: int | None

    @classmethod
    def from_query(cls, params) -> "AnalyticsFilters":
        parse_int = lambda key: int(params[key]) if params.get(key) else None
        parse_date = lambda key: date.fromisoformat(params[key]) if params.get(key) else None
        return cls(
            date_from=parse_date("date_from"),
            date_to=parse_date("date_to"),
            category_id=parse_int("category_id"),
            brand_id=parse_int("brand_id"),
            vendor_id=parse_int("vendor_id"),
            customer_id=parse_int("customer_id"),
            product_id=parse_int("product_id"),
        )

    def default_range(self) -> tuple[date, date]:
        """If the owner omits dates, use the last 30 days including today."""
        end = self.date_to or timezone.localdate()
        start = self.date_from or (end - timedelta(days=29))
        return start, end

    def previous_range(self) -> tuple[date, date]:
        """Equal-length window immediately before the selected range (growth %)."""
        start, end = self.default_range()
        length = (end - start).days + 1
        prev_end = start - timedelta(days=1)
        prev_start = prev_end - timedelta(days=length - 1)
        return prev_start, prev_end

    def filter_sales(self, qs: QuerySet[Sale]) -> QuerySet[Sale]:
        start, end = self.default_range()
        qs = qs.filter(invoice_date__gte=start, invoice_date__lte=end, is_cancelled=False)
        if self.customer_id:
            qs = qs.filter(customer_id=self.customer_id)
        if self.category_id or self.brand_id or self.vendor_id or self.product_id:
            qs = qs.filter(items__product__category_id=self.category_id) if self.category_id else qs
            qs = qs.filter(items__product__brand_id=self.brand_id) if self.brand_id else qs
            qs = qs.filter(items__batch__vendor_id=self.vendor_id) if self.vendor_id else qs
            qs = qs.filter(items__product_id=self.product_id) if self.product_id else qs
            qs = qs.distinct()
        return qs

    def filter_sale_items(self, qs: QuerySet[SaleItem]) -> QuerySet[SaleItem]:
        start, end = self.default_range()
        qs = qs.filter(sale__invoice_date__gte=start, sale__invoice_date__lte=end, sale__is_cancelled=False)
        if self.customer_id:
            qs = qs.filter(sale__customer_id=self.customer_id)
        if self.category_id:
            qs = qs.filter(product__category_id=self.category_id)
        if self.brand_id:
            qs = qs.filter(product__brand_id=self.brand_id)
        if self.vendor_id:
            qs = qs.filter(batch__vendor_id=self.vendor_id)
        if self.product_id:
            qs = qs.filter(product_id=self.product_id)
        return qs

    def filter_purchases(self, qs: QuerySet[Purchase]) -> QuerySet[Purchase]:
        start, end = self.default_range()
        qs = qs.filter(bill_date__gte=start, bill_date__lte=end, is_cancelled=False)
        if self.vendor_id:
            qs = qs.filter(vendor_id=self.vendor_id)
        if self.category_id or self.brand_id or self.product_id:
            qs = qs.filter(items__product__category_id=self.category_id) if self.category_id else qs
            qs = qs.filter(items__product__brand_id=self.brand_id) if self.brand_id else qs
            qs = qs.filter(items__product_id=self.product_id) if self.product_id else qs
            qs = qs.distinct()
        return qs

    def filter_purchase_items(self, qs: QuerySet[PurchaseItem]) -> QuerySet[PurchaseItem]:
        start, end = self.default_range()
        qs = qs.filter(purchase__bill_date__gte=start, purchase__bill_date__lte=end, purchase__is_cancelled=False)
        if self.vendor_id:
            qs = qs.filter(purchase__vendor_id=self.vendor_id)
        if self.category_id:
            qs = qs.filter(product__category_id=self.category_id)
        if self.brand_id:
            qs = qs.filter(product__brand_id=self.brand_id)
        if self.product_id:
            qs = qs.filter(product_id=self.product_id)
        return qs
