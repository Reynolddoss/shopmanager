"""HTTP endpoints for owner analytics. Numbers are computed in AnalyticsService."""

from __future__ import annotations

import csv
from io import StringIO

from django.core.cache import cache
from django.http import HttpResponse
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.analytics.query import AnalyticsFilters
from apps.analytics.services import analytics_service, insight_service


class AnalyticsBaseView(APIView):
    """Parse shared filters once. Optional 45s cache keyed by path + querystring."""

    cache_ttl = 45

    def filters(self, request) -> AnalyticsFilters:
        return AnalyticsFilters.from_query(request.query_params)

    def cached(self, request, key: str, builder):
        cache_key = f"analytics:{key}:{request.META.get('QUERY_STRING', '')}"
        payload = cache.get(cache_key)
        if payload is None:
            payload = builder()
            cache.set(cache_key, payload, self.cache_ttl)
        return Response(payload)


class SalesAnalyticsView(AnalyticsBaseView):
    def get(self, request):
        return self.cached(request, "sales", lambda: analytics_service.sales_summary(self.filters(request)))


class ProfitAnalyticsView(AnalyticsBaseView):
    def get(self, request):
        return self.cached(request, "profit", lambda: analytics_service.profit_summary(self.filters(request)))


class InventoryAnalyticsView(AnalyticsBaseView):
    def get(self, request):
        return self.cached(request, "inventory", analytics_service.inventory_summary)


class PurchaseAnalyticsView(AnalyticsBaseView):
    def get(self, request):
        return self.cached(request, "purchases", lambda: analytics_service.purchase_summary(self.filters(request)))


class VendorAnalyticsView(AnalyticsBaseView):
    def get(self, request):
        return self.cached(request, "vendors", lambda: analytics_service.vendor_summary(self.filters(request)))


class PriceHistoryView(AnalyticsBaseView):
    def get(self, request, product_id: int):
        return Response(analytics_service.price_history(product_id))


class BatchAnalyticsView(AnalyticsBaseView):
    def get(self, request):
        product_id = request.query_params.get("product_id")
        return Response(analytics_service.batch_summary(int(product_id) if product_id else None))


class DiscountAnalyticsView(AnalyticsBaseView):
    def get(self, request):
        return self.cached(request, "discounts", lambda: analytics_service.discount_summary(self.filters(request)))


class CustomerAnalyticsView(AnalyticsBaseView):
    def get(self, request):
        return self.cached(request, "customers", lambda: analytics_service.customer_summary(self.filters(request)))


class ExpenseAnalyticsView(AnalyticsBaseView):
    def get(self, request):
        return self.cached(request, "expenses", lambda: analytics_service.expense_summary(self.filters(request)))


class DashboardAnalyticsView(AnalyticsBaseView):
    cache_ttl = 20

    def get(self, request):
        return self.cached(request, "dashboard", analytics_service.dashboard)


class InsightsView(AnalyticsBaseView):
    def get(self, request):
        return Response({"insights": insight_service.build()})


class AnalyticsExportView(APIView):
    """CSV download of a named analytics table. Print/PDF is the browser print dialog."""

    def get(self, request, report: str):
        filters = AnalyticsFilters.from_query(request.query_params)
        rows, headers = self._rows(report, filters, request)
        buffer = StringIO()
        writer = csv.writer(buffer)
        writer.writerow(headers)
        for row in rows:
            writer.writerow([row.get(key, "") for key in headers])
        response = HttpResponse(buffer.getvalue(), content_type="text/csv")
        response["Content-Disposition"] = f'attachment; filename="{report}.csv"'
        return response

    def _rows(self, report: str, filters: AnalyticsFilters, request) -> tuple[list[dict], list[str]]:
        if report == "sales":
            data = analytics_service.sales_summary(filters)
            return data["top_products"], ["sku", "name", "qty", "revenue"]
        if report == "profit":
            data = analytics_service.profit_summary(filters)
            return data["by_product"], ["sku", "name", "gross_sales", "cogs", "gross_profit", "margin_percent"]
        if report == "inventory":
            data = analytics_service.inventory_summary()
            return data["stock_age"], ["sku", "lot_code", "remaining_quantity", "age_days", "value"]
        if report == "purchases":
            data = analytics_service.purchase_summary(filters)
            return data["top_products"], ["sku", "name", "qty", "total", "purchase_frequency"]
        if report == "vendors":
            data = analytics_service.vendor_summary(filters)
            return data["vendors"], [
                "name",
                "total_purchases",
                "best_historical_price",
                "average_purchase_price",
                "outstanding",
            ]
        if report == "customers":
            data = analytics_service.customer_summary(filters)
            return data["customers"], ["name", "purchase_value", "outstanding", "credit_utilization_percent"]
        if report == "expenses":
            data = analytics_service.expense_summary(filters)
            return data["by_category"], ["name", "total", "count"]
        if report == "batches":
            product_id = request.query_params.get("product_id")
            data = analytics_service.batch_summary(int(product_id) if product_id else None)
            return data["batches"], ["sku", "lot_code", "cost", "selling_price", "remaining_quantity", "age_days"]
        if report == "price-history":
            product_id = int(request.query_params.get("product_id") or 0)
            data = analytics_service.price_history(product_id)
            return data["history"], ["date", "vendor", "cost", "absolute_change", "percent_change"]
        return [], []
