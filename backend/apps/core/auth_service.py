"""
Shop registration and session login.

Each installed copy of the app owns one SQLite file and one shop. Registration
writes shop settings plus the first owner operator; later logins reuse Django
sessions on loopback only.
"""

from __future__ import annotations

from django.contrib.auth import login, logout
from django.contrib.auth.models import User
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from rest_framework.request import Request

from apps.core.models import ApplicationSettings, ShopOperator
from apps.core.services import audit_service


class AuthService:
    """Register the shop once, then authenticate operators with Django sessions."""

    def is_registered(self) -> bool:
        """True after the first owner account has been created."""
        return ShopOperator.objects.filter(is_owner=True).exists()

    def status(self, request: Request) -> dict:
        """Tell the UI whether to show register, login, or the main app."""
        registered = self.is_registered()
        user = request.user if getattr(request, "user", None) and request.user.is_authenticated else None
        shop = ApplicationSettings.objects.filter(singleton_key=1).first()
        operator = ShopOperator.objects.select_related("user").filter(user=user).first() if user else None
        return {
            "registered": registered,
            "authenticated": bool(user),
            "shop": {
                "name": shop.shop_name if shop else "",
                "gstin": shop.gstin if shop else "",
                "phone": shop.phone if shop else "",
                "ui_theme": getattr(shop, "ui_theme", None) or "midnight",
            }
            if registered and shop
            else None,
            "user": {
                "id": user.id,
                "username": user.username,
                "full_name": operator.full_name if operator else user.get_full_name() or user.username,
                "is_owner": operator.is_owner if operator else False,
            }
            if user
            else None,
        }

    @transaction.atomic
    def register(self, request: Request, payload: dict) -> dict:
        """Create owner user, operator profile, and shop settings atomically."""
        if self.is_registered():
            raise ValidationError({"detail": "This shop is already registered. Sign in instead."})
        username = payload["username"].strip().lower()
        user = User.objects.create_user(
            username=username,
            password=payload["password"],
            email=payload.get("email") or "",
            first_name=payload["owner_name"],
        )
        ShopOperator.objects.create(
            user=user,
            full_name=payload["owner_name"],
            phone=payload.get("phone") or "",
            is_owner=True,
        )
        prefix = (payload.get("invoice_prefix") or "SH").strip().upper()[:16] or "SH"
        settings_row, _created = ApplicationSettings.objects.get_or_create(
            singleton_key=1,
            defaults={"shop_name": payload["shop_name"]},
        )
        settings_row.shop_name = payload["shop_name"]
        settings_row.address = payload.get("address") or ""
        settings_row.gstin = payload.get("gstin") or ""
        settings_row.phone = payload.get("phone") or ""
        settings_row.invoice_prefix = prefix
        settings_row.sale_invoice_prefix = prefix
        extra = settings_row.extra if isinstance(settings_row.extra, dict) else {}
        extra["registered_at"] = timezone.now().isoformat()
        extra["owner_username"] = username
        settings_row.extra = extra
        settings_row.save()
        # Seed Electrician / General / … so customer forms work on day one.
        from apps.customers.services import customer_type_seed_service

        customer_type_seed_service.ensure_defaults()
        audit_service.record(
            action="shop_register",
            entity="shop",
            entity_id=settings_row.pk,
            new_data={"shop_name": settings_row.shop_name, "owner": username},
            actor=username,
        )
        login(request, user)
        return self.status(request)

    def login(self, request: Request, user: User) -> dict:
        """Start a session for an existing operator."""
        if not self.is_registered():
            raise ValidationError({"detail": "Register your shop before signing in."})
        login(request, user)
        operator = ShopOperator.objects.filter(user=user).first()
        audit_service.record(
            action="login",
            entity="user",
            entity_id=user.pk,
            actor=user.username,
            new_data={"full_name": operator.full_name if operator else user.username},
        )
        return self.status(request)

    def logout(self, request: Request) -> dict:
        """Clear the session cookie."""
        username = request.user.username if request.user.is_authenticated else ""
        logout(request)
        if username:
            audit_service.record(action="logout", entity="user", entity_id=username, actor=username)
        return {"authenticated": False}


auth_service = AuthService()
