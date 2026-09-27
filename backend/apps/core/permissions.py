"""API permissions for local session auth."""

from __future__ import annotations

from rest_framework.permissions import BasePermission


class IsAuthenticatedShopUser(BasePermission):
    """Require a logged-in operator after the shop has been registered."""

    def has_permission(self, request, view) -> bool:
        return bool(request.user and request.user.is_authenticated)


class AllowRegisterOnlyIfNew(BasePermission):
    """Registration endpoint is open only before the first owner exists."""

    def has_permission(self, request, view) -> bool:
        from apps.core.auth_service import auth_service

        return not auth_service.is_registered()
