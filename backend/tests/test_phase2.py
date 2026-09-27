"""Phase 2 inventory, finder, batch pricing, and stock-movement tests."""

from __future__ import annotations

from decimal import Decimal

import pytest
from django.db import IntegrityError, transaction
from django.test import Client

from apps.inventory.models import InventoryBatch, StockMovementType
from apps.inventory.services import inventory_service
from apps.products.models import Product, ProductAlias, ProductVendor, Tag
from apps.products.search import product_search_service
from apps.products.services import sku_suggestion_service
from tests.factories import CatalogFactory


@pytest.mark.django_db
class TestSkuSuggestion:
    def test_prefix_and_unique_serial(self) -> None:
        assert sku_suggestion_service.prefix_from_name("Conduit Pipes") == "CP"
        first = sku_suggestion_service.suggest("Conduit Pipes")
        assert first["sku"] == "CP-00001"
        CatalogFactory.product(sku="CP-00012")
        next_sku = sku_suggestion_service.suggest("Conduit Pipes")
        assert next_sku["sku"] == "CP-00013"

    def test_suggest_sku_endpoint(self, auth_client) -> None:
        CatalogFactory.product(sku="CP-00001")
        response = auth_client.get("/api/v1/products/suggest-sku/?name=Conduit%20Pipes")
        assert response.status_code == 200
        assert response.json()["sku"] == "CP-00002"
        assert response.json()["prefix"] == "CP"


@pytest.mark.django_db
class TestProductLifecycle:
    def test_create_product_and_reject_duplicate_sku(self) -> None:
        CatalogFactory.product(sku="SKU-DUP")
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                CatalogFactory.product(sku="SKU-DUP")

    def test_barcode_lookup(self, auth_client) -> None:
        product = CatalogFactory.product(sku="SKU-BAR")
        product.barcode = "8901234567890"
        product.save()
        response = auth_client.get("/api/v1/products/?search=8901234567890")
        assert response.status_code == 200
        assert response.json()["count"] == 1


@pytest.mark.django_db
class TestSmartFinder:
    def test_alias_category_brand_and_partial_search(self) -> None:
        product = CatalogFactory.product(sku="WIRE-25")
        ProductAlias.objects.create(product=product, term="house wire")
        tag = Tag.objects.create(name="frls")
        product.tags.add(tag)
        vendor = CatalogFactory.vendor()
        ProductVendor.objects.create(product=product, vendor=vendor, vendor_sku="V-25")
        qs = product_search_service.search("2.5 house")
        assert qs.filter(pk=product.pk).exists()
        qs_brand = product_search_service.search("polycab")
        assert qs_brand.filter(pk=product.pk).exists()
        qs_vendor = product_search_service.search("V-25")
        assert qs_vendor.filter(pk=product.pk).exists()

    def test_finder_endpoint_does_not_require_full_catalog(self, auth_client) -> None:
        CatalogFactory.product(sku="MCB-16")
        response = auth_client.get("/api/v1/products/finder/?q=mcb")
        assert response.status_code == 200
        payload = response.json()
        assert "results" in payload or isinstance(payload, list)


@pytest.mark.django_db
class TestBatchesAndPricing:
    def test_create_batch_preserves_previous_lot(self) -> None:
        product = CatalogFactory.product(sku="FAN-1200")
        vendor = CatalogFactory.vendor()
        first = inventory_service.create_batch(
            product=product,
            vendor=vendor,
            quantity=Decimal("4"),
            list_purchase_price=Decimal("1450"),
            selling_price=Decimal("1900"),
            safe_selling_price=Decimal("1750"),
            maximum_discount_percent=Decimal("8"),
            mrp=Decimal("2100"),
            pricing_mode="NEW",
            pricing_confirmed=True,
        )
        second = inventory_service.create_batch(
            product=product,
            vendor=vendor,
            quantity=Decimal("20"),
            list_purchase_price=Decimal("1580"),
            selling_price=Decimal("2050"),
            safe_selling_price=Decimal("1850"),
            maximum_discount_percent=Decimal("8"),
            pricing_mode="NEW",
            pricing_confirmed=True,
        )
        first.refresh_from_db()
        assert first.purchase_cost == Decimal("1450")
        assert first.remaining_quantity == Decimal("4")
        assert second.purchase_cost == Decimal("1580")
        assert InventoryBatch.objects.filter(product=product).count() == 2

    def test_previous_batch_detection_and_copy_pricing(self) -> None:
        product = CatalogFactory.product(sku="SW-6A")
        vendor = CatalogFactory.vendor()
        inventory_service.create_batch(
            product=product,
            vendor=vendor,
            quantity=Decimal("10"),
            list_purchase_price=Decimal("1450"),
            selling_price=Decimal("1900"),
            safe_selling_price=Decimal("1750"),
            maximum_discount_percent=Decimal("8"),
            pricing_confirmed=True,
        )
        comparison = inventory_service.compare_with_previous(product, Decimal("1580"))
        assert comparison["detected"] is True
        copied = inventory_service.create_batch(
            product=product,
            vendor=vendor,
            quantity=Decimal("5"),
            list_purchase_price=Decimal("1580"),
            pricing_mode="PREVIOUS",
            pricing_confirmed=True,
        )
        assert copied.selling_price == Decimal("1900")
        assert copied.safe_selling_price == Decimal("1750")

    def test_safe_price_and_discount_are_stored_on_batch(self) -> None:
        product = CatalogFactory.product(sku="LED-9")
        batch = inventory_service.create_batch(
            product=product,
            vendor=None,
            quantity=Decimal("12"),
            list_purchase_price=Decimal("80"),
            selling_price=Decimal("120"),
            safe_selling_price=Decimal("100"),
            maximum_discount_percent=Decimal("10"),
            pricing_confirmed=True,
        )
        assert batch.safe_selling_price == Decimal("100")
        assert batch.maximum_discount_percent == Decimal("10")

    def test_unconfirmed_pricing_is_rejected_when_previous_exists(self) -> None:
        product = CatalogFactory.product(sku="PIPE-20")
        inventory_service.create_batch(
            product=product,
            vendor=None,
            quantity=Decimal("1"),
            list_purchase_price=Decimal("50"),
            selling_price=Decimal("80"),
            safe_selling_price=Decimal("70"),
            maximum_discount_percent=Decimal("5"),
            pricing_confirmed=True,
        )
        with pytest.raises(Exception):
            inventory_service.create_batch(
                product=product,
                vendor=None,
                quantity=Decimal("1"),
                list_purchase_price=Decimal("55"),
                selling_price=Decimal("90"),
                safe_selling_price=Decimal("75"),
                maximum_discount_percent=Decimal("5"),
                pricing_confirmed=False,
            )


@pytest.mark.django_db
class TestStockMovements:
    def test_adjustment_records_before_and_after(self) -> None:
        product = CatalogFactory.product(sku="ADJ-1")
        batch = inventory_service.create_batch(
            product=product,
            vendor=None,
            quantity=Decimal("10"),
            list_purchase_price=Decimal("20"),
            selling_price=Decimal("30"),
            safe_selling_price=Decimal("25"),
            maximum_discount_percent=Decimal("5"),
            pricing_confirmed=True,
        )
        movement = inventory_service.apply_movement(
            batch=batch,
            movement_type=StockMovementType.DAMAGE,
            quantity_delta=Decimal("-2"),
            reason="Broken in transit",
        )
        batch.refresh_from_db()
        assert movement.quantity_before == Decimal("10")
        assert movement.quantity_after == Decimal("8")
        assert batch.remaining_quantity == Decimal("8")

    def test_movement_rolls_back_when_insufficient(self) -> None:
        product = CatalogFactory.product(sku="ADJ-2")
        batch = inventory_service.create_batch(
            product=product,
            vendor=None,
            quantity=Decimal("1"),
            list_purchase_price=Decimal("20"),
            selling_price=Decimal("30"),
            safe_selling_price=Decimal("25"),
            maximum_discount_percent=Decimal("5"),
            pricing_confirmed=True,
        )
        with pytest.raises(ValueError):
            inventory_service.apply_movement(
                batch=batch,
                movement_type=StockMovementType.ADJUSTMENT_OUT,
                quantity_delta=Decimal("-5"),
            )
        batch.refresh_from_db()
        assert batch.remaining_quantity == Decimal("1")
        assert batch.movements.count() == 1


@pytest.mark.django_db
class TestLowStockAndVendors:
    def test_low_and_out_of_stock_status(self) -> None:
        product = CatalogFactory.product(sku="LOW-1")
        product.reorder_level = Decimal("5")
        product.save()
        assert inventory_service.stock_status(product, Decimal("0")) == "out_of_stock"
        assert inventory_service.stock_status(product, Decimal("3")) == "low_stock"
        assert inventory_service.stock_status(product, Decimal("20")) == "in_stock"

    def test_vendor_relationship_cache(self) -> None:
        product = CatalogFactory.product(sku="VEN-1")
        vendor = CatalogFactory.vendor(name="Vendor A")
        inventory_service.create_batch(
            product=product,
            vendor=vendor,
            quantity=Decimal("2"),
            list_purchase_price=Decimal("1450"),
            selling_price=Decimal("1900"),
            safe_selling_price=Decimal("1750"),
            maximum_discount_percent=Decimal("8"),
            pricing_confirmed=True,
        )
        inventory_service.create_batch(
            product=product,
            vendor=vendor,
            quantity=Decimal("2"),
            list_purchase_price=Decimal("1580"),
            selling_price=Decimal("2050"),
            safe_selling_price=Decimal("1850"),
            maximum_discount_percent=Decimal("8"),
            pricing_confirmed=True,
        )
        link = ProductVendor.objects.get(product=product, vendor=vendor)
        assert link.last_purchase_price == Decimal("1580")
        assert link.lowest_historical_purchase_price == Decimal("1450")


@pytest.mark.django_db
class TestLargeFinderDataset:
    def test_finder_scales_past_full_table_scan_in_browser_terms(self) -> None:
        """Create a few hundred SKUs and assert token search stays server-side and correct."""
        base = CatalogFactory.product(sku="BULK-000")
        products = [
            Product(
                name=f"Anchor 6A switch {index}",
                sku=f"ANC-6A-{index:03d}",
                category=base.category,
                brand=base.brand,
                unit=base.unit,
            )
            for index in range(1, 201)
        ]
        Product.objects.bulk_create(products)
        needle = Product.objects.create(
            name="Polycab 2.5 sq mm FR House Wire",
            sku="NEEDLE-25",
            category=base.category,
            brand=base.brand,
            unit=base.unit,
        )
        ProductAlias.objects.create(product=needle, term="2.5 wire")
        matches = list(product_search_service.search("2.5 wire"))
        assert any(map(lambda row: row.sku == "NEEDLE-25", matches))
        assert len(matches) < 50
