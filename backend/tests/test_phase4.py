"""Phase 4 analytics: sales, profit from batch cost, inventory value, vendors, discounts."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest
from django.test import Client
from django.utils import timezone

from apps.analytics.query import AnalyticsFilters
from apps.analytics.services import analytics_service
from apps.customers.models import Customer
from apps.expenses.models import Expense, ExpenseCategory
from apps.purchases.services import purchase_service
from apps.sales.services import sale_service
from tests.factories import CatalogFactory


def _stock(sku: str, qty: str, cost: str, vendor_name: str, selling: str = "150", safe: str = "120"):
    product = CatalogFactory.product(sku=sku)
    vendor = CatalogFactory.vendor(vendor_name)
    purchase_service.create_purchase(
        {
            "vendor_id": vendor.id,
            "items": [
                {
                    "product_id": product.id,
                    "quantity": qty,
                    "base_purchase_price": cost,
                    "selling_price": selling,
                    "safe_selling_price": safe,
                    "maximum_discount_percent": "10",
                    "pricing_confirmed": True,
                }
            ],
        }
    )
    return product, vendor


@pytest.mark.django_db
class TestAnalyticsTotals:
    def test_sales_and_profit_use_batch_cost(self) -> None:
        today = timezone.localdate()
        product, _vendor = _stock("A4-WIRE", "10", "100", "A4 Vendor")
        customer = Customer.objects.create(name="A4 Cust", customer_type=CatalogFactory.customer_type("a4", "A4"))
        sale_service.create_sale(
            {
                "customer_id": customer.id,
                "payment_method": "CASH",
                "amount_paid": "0",
                "items": [{"product_id": product.id, "quantity": "2", "unit_price": "150"}],
            }
        )
        filters = AnalyticsFilters(today, today, None, None, None, None, None)
        sales = analytics_service.sales_summary(filters)
        profit = analytics_service.profit_summary(filters)
        assert sales["invoice_count"] == 1
        assert Decimal(profit["cost_of_goods"]) == Decimal("200.00")
        assert Decimal(profit["gross_profit"]) == Decimal("100.00")
        assert Decimal(profit["gross_sales"]) == Decimal("300.00")

    def test_date_filter_excludes_other_days(self) -> None:
        today = timezone.localdate()
        product, _vendor = _stock("A4-DATE", "5", "50", "Date Vendor")
        sale_service.create_sale(
            {
                "payment_method": "CASH",
                "amount_paid": "999",
                "invoice_date": today - timedelta(days=10),
                "items": [{"product_id": product.id, "quantity": "1", "unit_price": "150"}],
            }
        )
        filters = AnalyticsFilters(today, today, None, None, None, None, None)
        sales = analytics_service.sales_summary(filters)
        assert sales["invoice_count"] == 0

    def test_inventory_valuation_uses_remaining_batch_cost(self) -> None:
        product, _vendor = _stock("A4-VAL", "10", "80", "Val Vendor")
        sale_service.create_sale(
            {
                "payment_method": "CASH",
                "amount_paid": "999",
                "items": [{"product_id": product.id, "quantity": "4", "unit_price": "150"}],
            }
        )
        inventory = analytics_service.inventory_summary()
        assert Decimal(inventory["stock_value"]) == Decimal("480.00")

    def test_vendor_comparison_and_price_history(self) -> None:
        product = CatalogFactory.product(sku="A4-CMP")
        vendor_a = CatalogFactory.vendor("Vendor A")
        vendor_b = CatalogFactory.vendor("Vendor B")
        line = lambda vendor_id, cost: {
            "vendor_id": vendor_id,
            "items": [
                {
                    "product_id": product.id,
                    "quantity": "5",
                    "base_purchase_price": cost,
                    "selling_price": "200",
                    "safe_selling_price": "160",
                    "maximum_discount_percent": "0",
                    "pricing_confirmed": True,
                }
            ],
        }
        purchase_service.create_purchase(line(vendor_a.id, "1450"))
        purchase_service.create_purchase(line(vendor_b.id, "1480"))
        today = timezone.localdate()
        filters = AnalyticsFilters(today, today, None, None, None, None, product.id)
        vendors = analytics_service.vendor_summary(filters)
        assert len(vendors["product_comparison"]) == 2
        cheapest = vendors["product_comparison"][0]
        assert cheapest["vendor_id"] == vendor_a.id
        history = analytics_service.price_history(product.id)
        assert len(history["history"]) == 2
        assert Decimal(history["history"][1]["absolute_change"]) == Decimal("30.00")

    def test_customer_balance_and_discounts(self) -> None:
        today = timezone.localdate()
        product, _vendor = _stock("A4-DISC", "10", "100", "Disc Vendor", selling="200", safe="80")
        customer = Customer.objects.create(
            name="Disc Cust",
            customer_type=CatalogFactory.customer_type("d", "Dealer"),
            credit_limit=Decimal("10000"),
        )
        sale = sale_service.create_sale(
            {
                "customer_id": customer.id,
                "payment_method": "CREDIT",
                "amount_paid": "0",
                "items": [{"product_id": product.id, "quantity": "1", "unit_price": "180", "discount_amount": "20"}],
            }
        )
        filters = AnalyticsFilters(today, today, None, None, None, customer.id, None)
        customers = analytics_service.customer_summary(filters)
        discounts = analytics_service.discount_summary(filters)
        customer.refresh_from_db()
        assert customer.current_balance == sale.grand_total
        assert customers["customers"][0]["outstanding"] == str(sale.grand_total)
        assert Decimal(discounts["discount_total"]) == Decimal("20.00")

    def test_expenses_and_http_dashboard(self, auth_client) -> None:
        category = ExpenseCategory.objects.create(name="Rent")
        Expense.objects.create(category=category, expense_date=timezone.localdate(), amount=Decimal("5000"))
        today = timezone.localdate()
        filters = AnalyticsFilters(today, today, None, None, None, None, None)
        expenses = analytics_service.expense_summary(filters)
        assert Decimal(expenses["total_expenses"]) == Decimal("5000.00")
        dash = auth_client.get("/api/v1/analytics/dashboard/")
        assert dash.status_code == 200
        assert "today_sales" in dash.json()
        export = auth_client.get("/api/v1/analytics/export/expenses/")
        assert export.status_code == 200
        assert export["Content-Type"].startswith("text/csv")
