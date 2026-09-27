"""Customer master helpers: default types, phone normalisation, lookup."""

from __future__ import annotations

from django.db.models import Q

from apps.customers.models import Customer, CustomerType


class CustomerPhoneService:
    """Normalise and match mobile numbers so staff can find buyers quickly."""

    def digits_only(self, value: str | None) -> str:
        return "".join(filter(str.isdigit, value or ""))

    def matches_queryset(self, phone: str):
        """
        Find active customers whose phone, alternate phone, or name matches.

        Used at the counter when linking a bill to a returning buyer.
        """
        raw = (phone or "").strip()
        digits = self.digits_only(raw)
        if not digits and not raw:
            return Customer.objects.none()
        qs = Customer.objects.select_related("customer_type").filter(is_active=True)
        clauses = Q()
        if raw:
            clauses |= Q(phone__icontains=raw) | Q(alternate_phone__icontains=raw) | Q(name__icontains=raw)
        if digits:
            clauses |= Q(phone__icontains=digits) | Q(alternate_phone__icontains=digits)
        return qs.filter(clauses).distinct().order_by("name")


class CustomerTypeSeedService:
    """
    Ensure the shop has useful default buyer classifications.

    Types are data rows (not enums) so shops can add more later.
    """

    DEFAULTS = (
        ("general", "General"),
        ("electrician", "Electrician"),
        ("contractor", "Contractor"),
        ("builder", "Builder"),
        ("wholesale", "Wholesale"),
        ("retail", "Retail"),
        ("other", "Other"),
    )

    def ensure_defaults(self) -> list[CustomerType]:
        return list(
            map(
                lambda pair: CustomerType.objects.get_or_create(
                    code=pair[0],
                    defaults={"name": pair[1], "is_active": True},
                )[0],
                self.DEFAULTS,
            )
        )


customer_phone_service = CustomerPhoneService()
customer_type_seed_service = CustomerTypeSeedService()
