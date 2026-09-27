"""Helpers for authenticated API tests."""

from __future__ import annotations

from django.test import Client


class AuthFactory:
    """Register a test shop and return the authenticated Django test client."""

    DEFAULT_PAYLOAD = {
        "shop_name": "Test Electricals",
        "owner_name": "Test Owner",
        "username": "owner",
        "password": "testpass123",
        "confirm_password": "testpass123",
        "phone": "9999999999",
        "address": "123 Test Street",
        "gstin": "29ABCDE1234F1Z5",
        "invoice_prefix": "TS",
        "email": "owner@test.local",
    }

    @classmethod
    def register_shop(cls, client: Client | None = None, **overrides: object) -> Client:
        """Create the first owner account unless the shop is already registered."""
        test_client = client or Client()
        status = test_client.get("/api/v1/auth/status/")
        if status.status_code == 200 and status.json().get("registered"):
            return test_client
        payload = {**cls.DEFAULT_PAYLOAD, **overrides}
        response = test_client.post(
            "/api/v1/auth/register/",
            data=payload,
            content_type="application/json",
        )
        assert response.status_code == 201, response.content
        return test_client
