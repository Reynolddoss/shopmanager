"""Health, version, pagination, and basic catalog API coverage."""

from __future__ import annotations

import pytest
from django.test import Client

from tests.factories import CatalogFactory


@pytest.mark.django_db
class TestFoundationEndpoints:
    def test_health_and_sqlite(self) -> None:
        client = Client()
        response = client.get("/api/v1/health/")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "ok"
        assert body["database"] == "sqlite"
        assert body["integrity_check"] == "ok"

    def test_version(self) -> None:
        client = Client()
        response = client.get("/api/v1/version/")
        assert response.status_code == 200
        body = response.json()
        assert body["name"] == "Shop Manager"
        assert body["api"] == "v1"
        assert "version" in body

    def test_settings_round_trip(self, auth_client) -> None:
        created = auth_client.get("/api/v1/settings/")
        assert created.status_code == 200
        patched = auth_client.patch(
            "/api/v1/settings/",
            data={"shop_name": "MM Electricals Main"},
            content_type="application/json",
        )
        assert patched.status_code == 200
        assert patched.json()["shop_name"] == "MM Electricals Main"

    def test_settings_theme_round_trip(self, auth_client) -> None:
        patched = auth_client.patch(
            "/api/v1/settings/",
            data={"ui_theme": "slate"},
            content_type="application/json",
        )
        assert patched.status_code == 200
        assert patched.json()["ui_theme"] == "slate"
        status = auth_client.get("/api/v1/auth/status/").json()
        assert status["shop"]["ui_theme"] == "slate"
        rejected = auth_client.patch(
            "/api/v1/settings/",
            data={"ui_theme": "neon"},
            content_type="application/json",
        )
        assert rejected.status_code == 400



@pytest.mark.django_db
class TestCatalogApi:
    def test_create_and_search_product(self, auth_client) -> None:
        product = CatalogFactory.product(sku="API-1")
        listing = auth_client.get("/api/v1/products/?search=Polycab")
        assert listing.status_code == 200
        payload = listing.json()
        assert payload["count"] >= 1
        assert any(map(lambda row: row["sku"] == product.sku, payload["results"]))

    def test_vendor_list(self, auth_client) -> None:
        CatalogFactory.vendor(name="XYZ Supplies")
        response = auth_client.get("/api/v1/vendors/?search=XYZ")
        assert response.status_code == 200
        assert response.json()["count"] == 1
