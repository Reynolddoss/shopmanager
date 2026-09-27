"""Payment and ledger serializers."""

from __future__ import annotations

from rest_framework import serializers

from apps.payments.models import LedgerEntry, Payment


class LedgerEntrySerializer(serializers.ModelSerializer):
    class Meta:
        model = LedgerEntry
        fields = (
            "id",
            "party_type",
            "party_id",
            "entry_date",
            "entry_type",
            "debit",
            "credit",
            "reference_type",
            "reference_id",
            "notes",
        )


class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = (
            "id",
            "party_type",
            "party_id",
            "payment_date",
            "amount",
            "method",
            "reference",
            "notes",
            "created_at",
        )
        read_only_fields = ("id", "created_at")
