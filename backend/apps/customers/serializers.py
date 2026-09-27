from rest_framework import serializers

from apps.customers.models import Customer, CustomerType
from apps.customers.services import customer_phone_service, customer_type_seed_service
from apps.payments.models import LedgerEntryType, PartyType
from apps.payments.services import ledger_service


class CustomerTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomerType
        fields = ("id", "code", "name", "is_active", "created_at", "updated_at")
        read_only_fields = ("id", "created_at", "updated_at")


class CustomerSerializer(serializers.ModelSerializer):
    """
    Full customer profile for ledgers, billing linkage, and later analytics.

    Phone is the main practical identifier for returning buyers; type (Electrician,
    General, …) supports reporting. loyalty_points is stored but not awarded yet.
    """

    customer_type_name = serializers.CharField(source="customer_type.name", read_only=True, allow_null=True)
    phone_digits = serializers.SerializerMethodField()

    class Meta:
        model = Customer
        fields = (
            "id",
            "name",
            "phone",
            "alternate_phone",
            "address",
            "gstin",
            "customer_type",
            "customer_type_name",
            "credit_limit",
            "opening_balance",
            "current_balance",
            "loyalty_points",
            "notes",
            "is_active",
            "phone_digits",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "current_balance",
            "loyalty_points",
            "phone_digits",
            "created_at",
            "updated_at",
        )

    def get_phone_digits(self, obj: Customer) -> str:
        return customer_phone_service.digits_only(obj.phone)

    def validate_phone(self, value: str) -> str:
        return (value or "").strip()

    def validate(self, attrs: dict) -> dict:
        # Prefer a mobile on file so sales and frequent-buyer analytics can group correctly.
        name = attrs.get("name", getattr(self.instance, "name", ""))
        if not (name or "").strip():
            raise serializers.ValidationError({"name": "Name is required."})
        phone = attrs.get("phone")
        if phone is None and self.instance is not None:
            phone = self.instance.phone
        digits = customer_phone_service.digits_only(phone)
        if digits and len(digits) < 8:
            raise serializers.ValidationError({"phone": "Enter a fuller mobile number (at least 8 digits)."})
        return attrs

    def create(self, validated_data):
        customer_type_seed_service.ensure_defaults()
        if validated_data.get("customer_type") is None:
            general = CustomerType.objects.filter(code="general").first()
            if general is not None:
                validated_data["customer_type"] = general
        opening = validated_data.get("opening_balance") or 0
        validated_data["current_balance"] = 0
        customer = super().create(validated_data)
        if opening:
            ledger_service.post(
                party_type=PartyType.CUSTOMER,
                party_id=customer.id,
                entry_type=LedgerEntryType.OPENING,
                debit=opening if opening > 0 else 0,
                credit=(-opening if opening < 0 else 0),
                reference_type="customer",
                reference_id=customer.id,
                notes="Opening balance",
            )
        return customer
