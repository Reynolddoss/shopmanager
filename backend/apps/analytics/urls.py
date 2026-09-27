from django.urls import path

from apps.analytics.views import (
    BatchAnalyticsView,
    CustomerAnalyticsView,
    DashboardAnalyticsView,
    DiscountAnalyticsView,
    ExpenseAnalyticsView,
    InsightsView,
    InventoryAnalyticsView,
    PriceHistoryView,
    ProfitAnalyticsView,
    PurchaseAnalyticsView,
    SalesAnalyticsView,
    VendorAnalyticsView,
    AnalyticsExportView,
)

urlpatterns = [
    path("analytics/dashboard/", DashboardAnalyticsView.as_view(), name="analytics-dashboard"),
    path("analytics/sales/", SalesAnalyticsView.as_view(), name="analytics-sales"),
    path("analytics/profit/", ProfitAnalyticsView.as_view(), name="analytics-profit"),
    path("analytics/inventory/", InventoryAnalyticsView.as_view(), name="analytics-inventory"),
    path("analytics/purchases/", PurchaseAnalyticsView.as_view(), name="analytics-purchases"),
    path("analytics/vendors/", VendorAnalyticsView.as_view(), name="analytics-vendors"),
    path("analytics/discounts/", DiscountAnalyticsView.as_view(), name="analytics-discounts"),
    path("analytics/customers/", CustomerAnalyticsView.as_view(), name="analytics-customers"),
    path("analytics/expenses/", ExpenseAnalyticsView.as_view(), name="analytics-expenses"),
    path("analytics/batches/", BatchAnalyticsView.as_view(), name="analytics-batches"),
    path("analytics/insights/", InsightsView.as_view(), name="analytics-insights"),
    path("analytics/products/<int:product_id>/price-history/", PriceHistoryView.as_view(), name="analytics-price-history"),
    path("analytics/export/<str:report>/", AnalyticsExportView.as_view(), name="analytics-export"),
]
