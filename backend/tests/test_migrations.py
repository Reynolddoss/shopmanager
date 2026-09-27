"""Ensure Django migrations applied the expected business tables."""

from __future__ import annotations

import pytest
from django.db import connection


@pytest.mark.django_db
class TestMigrations:
    def test_migrate_creates_core_tables(self) -> None:
        table_names = connection.introspection.table_names()
        expected = [
            "core_applicationsettings",
            "core_auditlog",
            "products_product",
            "products_productalias",
            "products_productvendor",
            "vendors_vendor",
            "customers_customer",
            "inventory_inventorybatch",
            "inventory_stockmovement",
            "purchases_purchase",
            "purchases_purchaseitem",
            "sales_sale",
            "sales_saleitem",
            "payments_ledgerentry",
            "payments_payment",
            "core_documentsequence",
        ]
        missing = list(filter(lambda name: name not in table_names, expected))
        assert missing == []
