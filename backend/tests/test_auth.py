"""Registration, login, logout, and protected endpoint access."""

from __future__ import annotations

import pytest
from django.test import Client

from apps.core.models import ApplicationSettings, ShopOperator
from tests.auth_helpers import AuthFactory


@pytest.mark.django_db
class TestAuthFlow:
    def test_status_before_registration(self) -> None:
        client = Client()
        response = client.get("/api/v1/auth/status/")
        assert response.status_code == 200
        body = response.json()
        assert body["registered"] is False
        assert body["authenticated"] is False
        assert body["shop"] is None

    def test_register_creates_owner_and_shop(self) -> None:
        client = AuthFactory.register_shop()
        status = client.get("/api/v1/auth/status/").json()
        assert status["registered"] is True
        assert status["authenticated"] is True
        assert status["shop"]["name"] == "Test Electricals"
        assert ShopOperator.objects.filter(is_owner=True).count() == 1
        settings_row = ApplicationSettings.objects.get(singleton_key=1)
        assert settings_row.shop_name == "Test Electricals"
        assert settings_row.invoice_prefix == "TS"

    def test_register_rejected_when_already_registered(self) -> None:
        client = AuthFactory.register_shop()
        again = client.post(
            "/api/v1/auth/register/",
            data=AuthFactory.DEFAULT_PAYLOAD,
            content_type="application/json",
        )
        assert again.status_code in {400, 403}

    def test_login_and_logout(self) -> None:
        registered = AuthFactory.register_shop()
        registered.post("/api/v1/auth/logout/")
        logged_out = registered.get("/api/v1/auth/status/").json()
        assert logged_out["authenticated"] is False
        login = registered.post(
            "/api/v1/auth/login/",
            data={"username": "owner", "password": "testpass123"},
            content_type="application/json",
        )
        assert login.status_code == 200
        assert login.json()["authenticated"] is True
        logout = registered.post("/api/v1/auth/logout/")
        assert logout.status_code == 200
        assert logout.json()["authenticated"] is False

    def test_protected_settings_require_login(self) -> None:
        client = Client()
        blocked = client.get("/api/v1/settings/")
        assert blocked.status_code in {401, 403}
        authed = AuthFactory.register_shop()
        allowed = authed.get("/api/v1/settings/")
        assert allowed.status_code == 200

    def test_health_and_version_stay_public(self) -> None:
        client = Client()
        assert client.get("/api/v1/health/").status_code == 200
        assert client.get("/api/v1/version/").status_code == 200
