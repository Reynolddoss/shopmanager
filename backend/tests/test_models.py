"""Model validation, relationships, and SQLite constraints."""

from __future__ import annotations

from decimal import Decimal

import pytest
from django.db import IntegrityError, transaction

from apps.customers.models import Customer
from apps.inventory.models import InventoryBatch, StockMovementType
from apps.inventory.services import inventory_service
from apps.products.models import ProductAlias, ProductVendor
from tests.factories import CatalogFactory


@pytest.mark.django_db
class TestProductConstraints:
    def test_sku_must_be_unique(self) -> None:
        CatalogFactory.product(sku="SKU-1")
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                CatalogFactory.product(sku="SKU-1")

    def test_alias_unique_per_product(self) -> None:
        product = CatalogFactory.product(sku="SKU-ALIAS")
        ProductAlias.objects.create(product=product, term="2.5 wire")
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                ProductAlias.objects.create(product=product, term="2.5 wire")

    def test_product_vendor_unique_pair(self) -> None:
        product = CatalogFactory.product(sku="SKU-PV")
        vendor = CatalogFactory.vendor()
        ProductVendor.objects.create(product=product, vendor=vendor)
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                ProductVendor.objects.create(product=product, vendor=vendor)


@pytest.mark.django_db
class TestCustomerMaster:
    def test_customer_keeps_type_and_opening_balance(self) -> None:
        ctype = CatalogFactory.customer_type()
        customer = Customer.objects.create(
            name="Ramesh Electrician",
            phone="8888888888",
            customer_type=ctype,
            opening_balance=Decimal("1500.00"),
        )
        assert customer.customer_type.code == "retail"
        assert customer.is_active is True


@pytest.mark.django_db
class TestInventoryBatches:
    def test_previous_batch_is_detectable(self) -> None:
        product = CatalogFactory.product(sku="SKU-BATCH")
        vendor = CatalogFactory.vendor()
        first = InventoryBatch.objects.create(
            product=product,
            vendor=vendor,
            lot_code="001",
            purchase_date="2026-08-10",
            purchase_cost=Decimal("1450.00"),
            selling_price=Decimal("1900.00"),
            safe_selling_price=Decimal("1750.00"),
            remaining_quantity=Decimal("4"),
            original_quantity=Decimal("4"),
        )
        second = InventoryBatch.objects.create(
            product=product,
            vendor=vendor,
            lot_code="002",
            purchase_date="2026-08-24",
            purchase_cost=Decimal("1580.00"),
            selling_price=Decimal("2050.00"),
            safe_selling_price=Decimal("1850.00"),
            remaining_quantity=Decimal("20"),
            original_quantity=Decimal("20"),
        )
        previous = inventory_service.latest_previous_batch(product, excluding_id=second.pk)
        assert previous is not None
        assert previous.pk == first.pk
        assert previous.purchase_cost == Decimal("1450.00")

    def test_movement_is_atomic_and_refuses_negative_stock(self) -> None:
        product = CatalogFactory.product(sku="SKU-MOVE")
        batch = InventoryBatch.objects.create(
            product=product,
            lot_code="OPEN",
            purchase_cost=Decimal("100.00"),
            selling_price=Decimal("120.00"),
            safe_selling_price=Decimal("110.00"),
            remaining_quantity=Decimal("2"),
            original_quantity=Decimal("2"),
        )
        with pytest.raises(ValueError):
            inventory_service.apply_movement(
                batch=batch,
                movement_type=StockMovementType.SALE,
                quantity_delta=Decimal("-5"),
            )
        batch.refresh_from_db()
        assert batch.remaining_quantity == Decimal("2")
        assert batch.movements.count() == 0
