"""Serializers for health, version, and application settings."""

from __future__ import annotations

from rest_framework import serializers

from apps.core.models import ApplicationSettings


class ApplicationSettingsSerializer(serializers.ModelSerializer):
    """Validate settings updates; extra JSON remains a dict of primitives."""

    def validate_ui_theme(self, value: str) -> str:
        allowed = {"midnight", "slate", "paper"}
        normalized = (value or "midnight").strip().lower()
        if normalized not in allowed:
            raise serializers.ValidationError("Theme must be midnight, slate, or paper.")
        return normalized

    class Meta:
        model = ApplicationSettings
        fields = (
            "shop_name",
            "address",
            "gstin",
            "phone",
            "invoice_prefix",
            "currency",
            "default_tax_inclusive",
            "low_stock_threshold",
            "backup_retention_count",
            "scheduled_backup_enabled",
            "inventory_valuation_method",
            "sale_invoice_prefix",
            "purchase_invoice_prefix",
            "enforce_safe_selling_price",
            "ui_theme",
            "extra",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("created_at", "updated_at")
