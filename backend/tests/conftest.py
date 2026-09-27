"""Shared pytest fixtures."""

from __future__ import annotations

import pytest
from django.test import Client

from tests.auth_helpers import AuthFactory


@pytest.fixture
def auth_client() -> Client:
    """Django test client with an active owner session."""
    return AuthFactory.register_shop()
