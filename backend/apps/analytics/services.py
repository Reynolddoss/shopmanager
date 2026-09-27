"""
Owner analytics. Figures come from SQL aggregations on posted documents.

Profit uses SaleItem.batch_cost (lot cost at sale time), never the product's
current purchase price. Stock value is remaining_quantity * purchase_cost.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import timedelta
from decimal import Decimal

from django.db import DatabaseError
from django.db.models import Avg, Count, DecimalField, ExpressionWrapper, F, Max, Min, Q, Sum, Value
from django.db.models.functions import Coalesce, TruncMonth, TruncWeek, TruncYear
from django.utils import timezone

from apps.analytics.query import AnalyticsFilters, money, qty
from apps.customers.models import Customer
from apps.expenses.models import Expense
from apps.inventory.models import InventoryBatch
from apps.products.models import Product
from apps.purchases.models import Purchase, PurchaseItem
from apps.sales.models import Sale, SaleItem
from apps.vendors.models import Vendor

DEC = DecimalField(max_digits=18, decimal_places=4)
ZERO = Value(Decimal("0"), output_field=DEC)


class AnalyticsService:
    """Read-only owner intelligence. Does not post stock, sales, or payments."""

    def sales_summary(self, filters: AnalyticsFilters) -> dict:
        start, end = filters.default_range()
        sales = filters.filter_sales(Sale.objects.all())
        totals = sales.aggregate(
            invoice_count=Count("id"),
            gross=Coalesce(Sum("grand_total"), ZERO),
            taxable=Coalesce(Sum("taxable_amount"), ZERO),
            discounts=Coalesce(Sum("discount_amount"), ZERO),
        )
        invoice_count = totals["invoice_count"] or 0
        gross = totals["gross"]
        avg_bill = (gross / invoice_count) if invoice_count else Decimal("0")
        prev_start, prev_end = filters.previous_range()
        prev_gross = Sale.objects.filter(
            invoice_date__gte=prev_start,
            invoice_date__lte=prev_end,
            is_cancelled=False,
        ).aggregate(total=Coalesce(Sum("grand_total"), ZERO))["total"]
        growth = Decimal("0")
        if prev_gross:
            growth = ((gross - prev_gross) / prev_gross * Decimal("100")).quantize(Decimal("0.01"))
        items = filters.filter_sale_items(SaleItem.objects.all())
        top_products = list(
            items.values("product_id", "product__sku", "product__name")
            .annotate(qty=Sum("quantity"), revenue=Sum("line_total"))
            .order_by("-qty")[:10]
        )
        top_brands = list(
            items.values("product__brand__name")
            .annotate(qty=Sum("quantity"), revenue=Sum("line_total"))
            .order_by("-revenue")[:10]
        )
        top_categories = list(
            items.values("product__category__name")
            .annotate(qty=Sum("quantity"), revenue=Sum("line_total"))
            .order_by("-revenue")[:10]
        )
        top_customers = list(
            sales.exclude(customer_id=None)
            .values("customer_id", "customer__name")
            .annotate(invoice_count=Count("id"), revenue=Sum("grand_total"))
            .order_by("-revenue")[:10]
        )
        return {
            "date_from": str(start),
            "date_to": str(end),
            "invoice_count": invoice_count,
            "gross_sales": money(gross),
            "taxable_sales": money(totals["taxable"]),
            "discounts": money(totals["discounts"]),
            "average_bill_value": money(avg_bill),
            "previous_period_sales": money(prev_gross),
            "sales_growth_percent": money(growth),
            "series": {
                "daily": self._sale_series_by_date(sales),
                "weekly": self._sale_series(sales, TruncWeek("invoice_date")),
                "monthly": self._sale_series(sales, TruncMonth("invoice_date")),
                "yearly": self._sale_series(sales, TruncYear("invoice_date")),
            },
            "top_products": [
                {
                    "product_id": row["product_id"],
                    "sku": row["product__sku"],
                    "name": row["product__name"],
                    "qty": qty(row["qty"]),
                    "revenue": money(row["revenue"]),
                }
                for row in top_products
            ],
            "top_brands": [
                {"name": row["product__brand__name"] or "Unspecified", "qty": qty(row["qty"]), "revenue": money(row["revenue"])}
                for row in top_brands
            ],
            "top_categories": [
                {
                    "name": row["product__category__name"] or "Unspecified",
                    "qty": qty(row["qty"]),
                    "revenue": money(row["revenue"]),
                }
                for row in top_categories
            ],
            "top_customers": [
                {
                    "id": row["customer_id"],
                    "name": row["customer__name"],
                    "invoice_count": row["invoice_count"],
                    "revenue": money(row["revenue"]),
                }
                for row in top_customers
            ],
        }

    def _sale_series_by_date(self, sales) -> list[dict]:
        rows = (
            sales.values("invoice_date")
            .annotate(invoice_count=Count("id"), total=Sum("grand_total"))
            .order_by("invoice_date")
        )
        return [
            {"period": str(row["invoice_date"]), "invoice_count": row["invoice_count"], "total": money(row["total"])}
            for row in rows
        ]

    def _sale_series(self, sales, bucket) -> list[dict]:
        """
        Week/month/year buckets. SQLite Trunc* can fail; then we skip the series
        instead of breaking the whole sales payload.
        """
        try:
            rows = (
                sales.annotate(bucket=bucket)
                .values("bucket")
                .annotate(invoice_count=Count("id"), total=Sum("grand_total"))
                .order_by("bucket")
            )
            return [
                {"period": str(row["bucket"])[:10], "invoice_count": row["invoice_count"], "total": money(row["total"])}
                for row in rows
            ]
        except DatabaseError:
            return []

    def profit_summary(self, filters: AnalyticsFilters) -> dict:
        """
        revenue_ex_gst = quantity * unit_price - discount_amount
        cogs = quantity * batch_cost  (historical lot cost on the sale line)
        """
        items = filters.filter_sale_items(SaleItem.objects.all())
        # COGS uses the sale-line snapshot first, then the lot's purchase_cost.
        revenue_expr = ExpressionWrapper(F("quantity") * F("unit_price") - F("discount_amount"), output_field=DEC)
        cogs_expr = ExpressionWrapper(
            F("quantity") * Coalesce(F("batch_cost"), F("batch__purchase_cost")),
            output_field=DEC,
        )
        line_rows = list(
            items.values("quantity", "unit_price", "discount_amount", "batch_cost", "batch__purchase_cost")
        )
        line_cogs = lambda row: row["quantity"] * (row["batch_cost"] or row["batch__purchase_cost"] or Decimal("0"))
        totals = {
            "gross_sales": sum((row["quantity"] * row["unit_price"] - row["discount_amount"] for row in line_rows), Decimal("0")),
            "discounts": sum((row["discount_amount"] for row in line_rows), Decimal("0")),
            "cogs": sum((line_cogs(row) for row in line_rows), Decimal("0")),
        }
        annotated = items.annotate(revenue=revenue_expr, cogs=cogs_expr)
        profit = totals["gross_sales"] - totals["cogs"]
        margin = Decimal("0")
        if totals["gross_sales"]:
            margin = (profit / totals["gross_sales"] * Decimal("100")).quantize(Decimal("0.01"))

        def pack(rows, name_key: str, extra: dict | None = None) -> list[dict]:
            packed = []
            for row in rows:
                gp = row["gross_sales"] - row["cogs"]
                packed.append(
                    {
                        "name": row[name_key] or "Unspecified",
                        "gross_sales": money(row["gross_sales"]),
                        "cogs": money(row["cogs"]),
                        "gross_profit": money(gp),
                        "margin_percent": money((gp / row["gross_sales"] * Decimal("100")) if row["gross_sales"] else 0),
                        **(extra(row) if extra else {}),
                    }
                )
            return packed

        by_product = list(
            annotated.values("product_id", "product__sku", "product__name")
            .annotate(gross_sales=Sum("revenue"), cogs=Sum("cogs"))
            .order_by("-gross_sales")[:20]
        )
        by_category = list(
            annotated.values("product__category__name")
            .annotate(gross_sales=Sum("revenue"), cogs=Sum("cogs"))
            .order_by("-gross_sales")[:20]
        )
        by_brand = list(
            annotated.values("product__brand__name")
            .annotate(gross_sales=Sum("revenue"), cogs=Sum("cogs"))
            .order_by("-gross_sales")[:20]
        )
        return {
            "gross_sales": money(totals["gross_sales"]),
            "discounts": money(totals["discounts"]),
            "cost_of_goods": money(totals["cogs"]),
            "gross_profit": money(profit),
            "gross_margin_percent": money(margin),
            "by_product": pack(
                by_product,
                "product__name",
                extra=lambda row: {"product_id": row["product_id"], "sku": row["product__sku"]},
            ),
            "by_category": pack(by_category, "product__category__name"),
            "by_brand": pack(by_brand, "product__brand__name"),
        }

    def inventory_summary(self) -> dict:
        today = timezone.localdate()
        lots = InventoryBatch.objects.filter(remaining_quantity__gt=0).select_related("product")
        on_hand = lots.aggregate(
            qty=Coalesce(Sum("remaining_quantity"), ZERO),
            value=Coalesce(
                Sum(ExpressionWrapper(F("remaining_quantity") * F("purchase_cost"), output_field=DEC)),
                ZERO,
            ),
        )
        products = Product.objects.filter(is_active=True).annotate(
            on_hand=Coalesce(Sum("batches__remaining_quantity"), ZERO),
        )
        low = products.filter(on_hand__gt=0).filter(
            Q(on_hand__lte=F("reorder_level")) | Q(on_hand__lte=F("min_stock_quantity"))
        ).count()
        out = products.filter(on_hand__lte=0).count()
        last_90 = today - timedelta(days=90)
        sold_90 = {
            row["product_id"]: row["qty"]
            for row in SaleItem.objects.filter(sale__invoice_date__gte=last_90, sale__is_cancelled=False)
            .values("product_id")
            .annotate(qty=Sum("quantity"))
        }
        fast = sorted(sold_90.items(), key=lambda pair: pair[1], reverse=True)[:10]
        in_stock_ids = set(products.filter(on_hand__gt=0).values_list("id", flat=True))
        dead_ids = list(in_stock_ids - set(sold_90.keys()))
        slow_ids = [pid for pid, _sold in sorted(sold_90.items(), key=lambda pair: pair[1])[:10]]
        wanted = [pid for pid, _sold in fast] + dead_ids[:20] + slow_ids
        product_map = {item.id: item for item in Product.objects.filter(pk__in=wanted)}

        def named(ids: list[int]) -> list[dict]:
            return [
                {
                    "product_id": pid,
                    "sku": product_map[pid].sku,
                    "name": product_map[pid].name,
                    "sold_qty": qty(sold_90.get(pid, 0)),
                }
                for pid in ids
                if pid in product_map
            ]

        aged = []
        for lot in lots.order_by("purchase_date")[:50]:
            age = (today - lot.purchase_date).days if lot.purchase_date else 0
            aged.append(
                {
                    "batch_id": lot.id,
                    "lot_code": lot.lot_code,
                    "product_id": lot.product_id,
                    "sku": lot.product.sku,
                    "remaining_quantity": qty(lot.remaining_quantity),
                    "age_days": age,
                    "value": money(lot.remaining_quantity * lot.purchase_cost),
                }
            )
        sold_qty = sum(sold_90.values(), Decimal("0"))
        on_hand_qty = on_hand["qty"] or Decimal("0")
        turnover = (sold_qty / on_hand_qty).quantize(Decimal("0.01")) if on_hand_qty else Decimal("0")
        return {
            "on_hand_quantity": qty(on_hand["qty"]),
            "stock_value": money(on_hand["value"]),
            "valuation_method": "FIFO",
            "low_stock_count": low,
            "out_of_stock_count": out,
            "stock_turnover_90d": money(turnover),
            "fast_moving": named([pid for pid, _sold in fast]),
            "slow_moving": named(slow_ids),
            "dead_stock": named(dead_ids[:20]),
            "stock_age": aged,
        }

    def purchase_summary(self, filters: AnalyticsFilters) -> dict:
        purchases = filters.filter_purchases(Purchase.objects.all())
        items = filters.filter_purchase_items(PurchaseItem.objects.all())
        totals = purchases.aggregate(bill_count=Count("id"), total=Coalesce(Sum("grand_total"), ZERO))
        by_vendor = list(
            purchases.values("vendor_id", "vendor__name")
            .annotate(total=Sum("grand_total"), bills=Count("id"))
            .order_by("-total")[:20]
        )
        by_category = list(
            items.values("product__category__name").annotate(total=Sum("line_total")).order_by("-total")[:20]
        )
        by_brand = list(items.values("product__brand__name").annotate(total=Sum("line_total")).order_by("-total")[:20])
        top_products = list(
            items.values("product_id", "product__sku", "product__name")
            .annotate(qty=Sum("quantity"), total=Sum("line_total"), bills=Count("purchase_id", distinct=True))
            .order_by("-qty")[:20]
        )
        series = (
            purchases.annotate(bucket=TruncMonth("bill_date"))
            .values("bucket")
            .annotate(total=Sum("grand_total"), bills=Count("id"))
            .order_by("bucket")
        )
        return {
            "bill_count": totals["bill_count"] or 0,
            "total_purchases": money(totals["total"]),
            "trend_monthly": [
                {"period": str(row["bucket"])[:7], "total": money(row["total"]), "bills": row["bills"]}
                for row in series
            ],
            "by_vendor": [
                {
                    "id": row["vendor_id"],
                    "name": row["vendor__name"],
                    "total": money(row["total"]),
                    "bills": row["bills"],
                }
                for row in by_vendor
            ],
            "by_category": [
                {"name": row["product__category__name"] or "Unspecified", "total": money(row["total"])}
                for row in by_category
            ],
            "by_brand": [
                {"name": row["product__brand__name"] or "Unspecified", "total": money(row["total"])} for row in by_brand
            ],
            "top_products": [
                {
                    "product_id": row["product_id"],
                    "sku": row["product__sku"],
                    "name": row["product__name"],
                    "qty": qty(row["qty"]),
                    "total": money(row["total"]),
                    "purchase_frequency": row["bills"],
                }
                for row in top_products
            ],
        }

    def vendor_summary(self, filters: AnalyticsFilters) -> dict:
        items = filters.filter_purchase_items(PurchaseItem.objects.all())
        vendors = list(
            items.values("purchase__vendor_id", "purchase__vendor__name")
            .annotate(
                total=Sum("line_total"),
                bills=Count("purchase_id", distinct=True),
                products=Count("product_id", distinct=True),
                average_price=Avg("effective_purchase_cost"),
                best_price=Min("effective_purchase_cost"),
                last_price=Max("effective_purchase_cost"),
            )
            .order_by("-total")
        )
        outstanding = {vendor.id: vendor.current_balance for vendor in Vendor.objects.all()}
        last_dates = {
            row["vendor_id"]: row["last"]
            for row in Purchase.objects.filter(is_cancelled=False).values("vendor_id").annotate(last=Max("bill_date"))
        }
        comparison = []
        if filters.product_id:
            comparison = list(
                InventoryBatch.objects.filter(product_id=filters.product_id, vendor_id__isnull=False)
                .values("vendor_id", "vendor__name")
                .annotate(
                    average_price=Avg("purchase_cost"),
                    best_price=Min("purchase_cost"),
                    last_price=Max("purchase_cost"),
                    lots=Count("id"),
                )
                .order_by("best_price")
            )
        return {
            "vendors": [
                {
                    "id": row["purchase__vendor_id"],
                    "name": row["purchase__vendor__name"],
                    "total_purchases": money(row["total"]),
                    "products_supplied": row["products"],
                    "average_purchase_price": money(row["average_price"]),
                    "best_historical_price": money(row["best_price"]),
                    "last_purchase_price": money(row["last_price"]),
                    "purchase_frequency": row["bills"],
                    "outstanding": money(outstanding.get(row["purchase__vendor_id"], 0)),
                    "last_purchase_date": str(last_dates.get(row["purchase__vendor_id"]) or ""),
                }
                for row in vendors
            ],
            "product_comparison": [
                {
                    "vendor_id": row["vendor_id"],
                    "vendor_name": row["vendor__name"],
                    "average_price": money(row["average_price"]),
                    "best_price": money(row["best_price"]),
                    "last_price": money(row["last_price"]),
                    "lots": row["lots"],
                }
                for row in comparison
            ],
        }

    def price_history(self, product_id: int) -> dict:
        lots = list(
            InventoryBatch.objects.filter(product_id=product_id)
            .select_related("vendor", "product")
            .order_by("purchase_date", "id")
        )
        points = []
        previous = None
        for lot in lots:
            change = Decimal("0")
            percent = Decimal("0")
            if previous is not None:
                change = lot.purchase_cost - previous
                if previous:
                    percent = (change / previous * Decimal("100")).quantize(Decimal("0.01"))
            points.append(
                {
                    "batch_id": lot.id,
                    "lot_code": lot.lot_code,
                    "date": str(lot.purchase_date or ""),
                    "vendor": lot.vendor.name if lot.vendor_id else "",
                    "cost": money(lot.purchase_cost),
                    "absolute_change": money(change),
                    "percent_change": money(percent),
                }
            )
            previous = lot.purchase_cost
        product = Product.objects.filter(pk=product_id).first()
        return {
            "product_id": product_id,
            "sku": product.sku if product else "",
            "name": product.name if product else "",
            "history": points,
        }

    def batch_summary(self, product_id: int | None = None) -> dict:
        today = timezone.localdate()
        lots = InventoryBatch.objects.filter(is_open=True).select_related("product", "vendor")
        if product_id:
            lots = lots.filter(product_id=product_id)
        rows = []
        for lot in lots.order_by("product_id", "purchase_date"):
            age = (today - lot.purchase_date).days if lot.purchase_date else 0
            margin = lot.selling_price - lot.purchase_cost
            margin_pct = (margin / lot.selling_price * Decimal("100")) if lot.selling_price else Decimal("0")
            rows.append(
                {
                    "batch_id": lot.id,
                    "product_id": lot.product_id,
                    "sku": lot.product.sku,
                    "lot_code": lot.lot_code,
                    "vendor": lot.vendor.name if lot.vendor_id else "",
                    "remaining_quantity": qty(lot.remaining_quantity),
                    "original_quantity": qty(lot.original_quantity),
                    "cost": money(lot.purchase_cost),
                    "selling_price": money(lot.selling_price),
                    "safe_selling_price": money(lot.safe_selling_price),
                    "margin": money(margin),
                    "margin_percent": money(margin_pct),
                    "age_days": age,
                }
            )
        return {"batches": rows}

    def discount_summary(self, filters: AnalyticsFilters) -> dict:
        items = filters.filter_sale_items(SaleItem.objects.select_related("sale__customer__customer_type", "product"))
        totals = items.aggregate(
            avg_discount=Coalesce(Avg("discount_amount"), ZERO),
            discount_total=Coalesce(Sum("discount_amount"), ZERO),
            overrides=Count("id", filter=Q(below_safe_override=True)),
        )
        revenue_expr = ExpressionWrapper(F("quantity") * F("unit_price") - F("discount_amount"), output_field=DEC)
        cogs_expr = ExpressionWrapper(F("quantity") * F("batch_cost"), output_field=DEC)
        annotated = items.annotate(revenue=revenue_expr, cogs=cogs_expr)
        by_product = list(
            annotated.values("product_id", "product__sku", "product__name")
            .annotate(discount_total=Sum("discount_amount"), revenue=Sum("revenue"), cogs=Sum("cogs"), lines=Count("id"))
            .order_by("-discount_total")[:20]
        )
        by_customer = list(
            annotated.exclude(sale__customer_id=None)
            .values("sale__customer_id", "sale__customer__name")
            .annotate(discount_total=Sum("discount_amount"), revenue=Sum("revenue"))
            .order_by("-discount_total")[:20]
        )
        by_type = list(
            annotated.exclude(sale__customer__customer_type_id=None)
            .values("sale__customer__customer_type__name")
            .annotate(discount_total=Sum("discount_amount"), revenue=Sum("revenue"))
            .order_by("-discount_total")
        )
        eroders = [
            row
            for row in by_product
            if row["revenue"] and (row["revenue"] - row["cogs"]) / row["revenue"] < Decimal("0.10") and row["discount_total"]
        ]
        return {
            "average_discount": money(totals["avg_discount"]),
            "discount_total": money(totals["discount_total"]),
            "safe_price_overrides": totals["overrides"] or 0,
            "by_product": [
                {
                    "product_id": row["product_id"],
                    "sku": row["product__sku"],
                    "name": row["product__name"],
                    "discount_total": money(row["discount_total"]),
                    "gross_profit": money(row["revenue"] - row["cogs"]),
                    "lines": row["lines"],
                }
                for row in by_product
            ],
            "by_customer": [
                {
                    "id": row["sale__customer_id"],
                    "name": row["sale__customer__name"],
                    "discount_total": money(row["discount_total"]),
                    "revenue": money(row["revenue"]),
                }
                for row in by_customer
            ],
            "by_customer_type": [
                {
                    "name": row["sale__customer__customer_type__name"],
                    "discount_total": money(row["discount_total"]),
                    "revenue": money(row["revenue"]),
                }
                for row in by_type
            ],
            "margin_eroders": [
                {
                    "sku": row["product__sku"],
                    "name": row["product__name"],
                    "discount_total": money(row["discount_total"]),
                    "margin_percent": money(
                        ((row["revenue"] - row["cogs"]) / row["revenue"] * Decimal("100")) if row["revenue"] else 0
                    ),
                }
                for row in eroders
            ],
        }

    def customer_summary(self, filters: AnalyticsFilters) -> dict:
        sales = filters.filter_sales(Sale.objects.exclude(customer_id=None))
        rows = list(
            sales.values(
                "customer_id",
                "customer__name",
                "customer__phone",
                "customer__customer_type__name",
                "customer__credit_limit",
            )
            .annotate(revenue=Sum("grand_total"), invoices=Count("id"), paid=Sum("amount_paid"))
            .order_by("-invoices", "-revenue")[:50]
        )
        balances = {customer.id: customer for customer in Customer.objects.all()}
        return {
            "customers": [
                {
                    "id": row["customer_id"],
                    "name": row["customer__name"],
                    "phone": row["customer__phone"] or "",
                    "customer_type": row["customer__customer_type__name"] or "",
                    "purchase_value": money(row["revenue"]),
                    "invoices": row["invoices"],
                    "paid": money(row["paid"]),
                    "outstanding": money(balances[row["customer_id"]].current_balance)
                    if row["customer_id"] in balances
                    else "0.00",
                    "credit_limit": money(row["customer__credit_limit"]),
                    "credit_utilization_percent": money(
                        (
                            balances[row["customer_id"]].current_balance
                            / row["customer__credit_limit"]
                            * Decimal("100")
                        )
                        if row["customer_id"] in balances and row["customer__credit_limit"]
                        else 0
                    ),
                }
                for row in rows
            ]
        }

    def expense_summary(self, filters: AnalyticsFilters) -> dict:
        start, end = filters.default_range()
        qs = Expense.objects.filter(expense_date__gte=start, expense_date__lte=end)
        totals = qs.aggregate(total=Coalesce(Sum("amount"), ZERO), count=Count("id"))
        by_category = list(
            qs.values("category__name").annotate(total=Sum("amount"), count=Count("id")).order_by("-total")
        )
        monthly = list(
            qs.annotate(bucket=TruncMonth("expense_date"))
            .values("bucket")
            .annotate(total=Sum("amount"))
            .order_by("bucket")
        )
        return {
            "total_expenses": money(totals["total"]),
            "count": totals["count"] or 0,
            "by_category": [
                {"name": row["category__name"], "total": money(row["total"]), "count": row["count"]} for row in by_category
            ],
            "monthly": [{"period": str(row["bucket"])[:7], "total": money(row["total"])} for row in monthly],
        }

    def dashboard(self) -> dict:
        today = timezone.localdate()
        day_filters = AnalyticsFilters(today, today, None, None, None, None, None)
        sales = self.sales_summary(day_filters)
        profit = self.profit_summary(day_filters)
        purchases = Purchase.objects.filter(bill_date=today, is_cancelled=False).aggregate(
            total=Coalesce(Sum("grand_total"), ZERO)
        )
        inventory = self.inventory_summary()
        receivables = Customer.objects.aggregate(total=Coalesce(Sum("current_balance"), ZERO))["total"]
        payables = Vendor.objects.aggregate(total=Coalesce(Sum("current_balance"), ZERO))["total"]
        recent = list(
            Sale.objects.filter(is_cancelled=False)
            .order_by("-id")[:8]
            .values("id", "invoice_number", "invoice_date", "grand_total", "customer__name")
        )
        return {
            "today_sales": sales["gross_sales"],
            "today_profit": profit["gross_profit"],
            "today_purchases": money(purchases["total"]),
            "today_invoices": sales["invoice_count"],
            "receivables": money(receivables),
            "payables": money(payables),
            "stock_value": inventory["stock_value"],
            "low_stock_count": inventory["low_stock_count"],
            "top_products": sales["top_products"][:5],
            "recent_sales": [
                {
                    "id": row["id"],
                    "invoice_number": row["invoice_number"],
                    "date": str(row["invoice_date"]),
                    "customer": row["customer__name"] or "Walk-in",
                    "total": money(row["grand_total"]),
                }
                for row in recent
            ],
            "insights": insight_service.build()[:8],
        }


class InsightService:
    """Fact-based alerts only. No forecasts."""

    def build(self) -> list[dict]:
        today = timezone.localdate()
        month_start = today.replace(day=1)
        month_filters = AnalyticsFilters(month_start, today, None, None, None, None, None)
        analytics = AnalyticsService()
        insights: list[dict] = []
        inventory = analytics.inventory_summary()
        if inventory["low_stock_count"]:
            insights.append(
                {
                    "code": "LOW_STOCK",
                    "message": f"{inventory['low_stock_count']} products are at or below reorder level.",
                }
            )
        if inventory["dead_stock"]:
            insights.append(
                {
                    "code": "DEAD_STOCK",
                    "message": f"{len(inventory['dead_stock'])} products have had no sales in 90 days.",
                }
            )
        receivables = Customer.objects.aggregate(total=Coalesce(Sum("current_balance"), ZERO))["total"]
        if receivables:
            insights.append(
                {"code": "RECEIVABLES", "message": f"₹{money(receivables)} is outstanding from customers."}
            )
        profit = analytics.profit_summary(month_filters)
        brands = profit["by_brand"]
        if brands and Decimal(profit["gross_profit"]) > 0:
            top = brands[0]
            share = Decimal(top["gross_profit"]) / Decimal(profit["gross_profit"]) * Decimal("100")
            insights.append(
                {
                    "code": "BRAND_PROFIT",
                    "message": f"{top['name']} products generated {money(share)}% of gross profit this month.",
                }
            )
        grouped: dict[int, list] = defaultdict(list)
        for lot in InventoryBatch.objects.select_related("product", "vendor").order_by("product_id", "purchase_date", "id"):
            grouped[lot.product_id].append(lot)
        for product_lots in grouped.values():
            if len(product_lots) < 2:
                continue
            prev, last = product_lots[-2], product_lots[-1]
            if not prev.purchase_cost:
                continue
            percent = (last.purchase_cost - prev.purchase_cost) / prev.purchase_cost * Decimal("100")
            if percent >= Decimal("5"):
                insights.append(
                    {
                        "code": "PRICE_UP",
                        "message": (
                            f"{last.product.sku} purchase cost increased {money(percent)}% "
                            f"({money(prev.purchase_cost)} → {money(last.purchase_cost)})."
                        ),
                    }
                )
                cheaper = (
                    InventoryBatch.objects.filter(product_id=last.product_id, vendor_id__isnull=False)
                    .values("vendor__name")
                    .annotate(best=Min("purchase_cost"))
                    .order_by("best")
                    .first()
                )
                if cheaper and cheaper["vendor__name"]:
                    insights.append(
                        {
                            "code": "BEST_VENDOR",
                            "message": (
                                f"Vendor {cheaper['vendor__name']} currently holds the lowest recorded "
                                f"price for {last.product.sku} (₹{money(cheaper['best'])})."
                            ),
                        }
                    )
                break
        return insights


analytics_service = AnalyticsService()
insight_service = InsightService()
