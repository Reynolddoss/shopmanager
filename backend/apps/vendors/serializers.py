from rest_framework import serializers

from apps.payments.models import LedgerEntryType, PartyType
from apps.payments.services import ledger_service
from apps.vendors.models import Vendor


class VendorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Vendor
        fields = (
            "id",
            "name",
            "phone",
            "alternate_phone",
            "email",
            "address",
            "gstin",
            "contact_person",
            "payment_terms",
            "opening_balance",
            "current_balance",
            "notes",
            "is_active",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "current_balance", "created_at", "updated_at")

    def create(self, validated_data):
        opening = validated_data.get("opening_balance") or 0
        validated_data["current_balance"] = 0
        vendor = super().create(validated_data)
        if opening:
            ledger_service.post(
                party_type=PartyType.VENDOR,
                party_id=vendor.id,
                entry_type=LedgerEntryType.OPENING,
                credit=opening if opening > 0 else 0,
                debit=(-opening if opening < 0 else 0),
                reference_type="vendor",
                reference_id=vendor.id,
                notes="Opening balance",
            )
        return vendor
