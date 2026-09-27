"""
Ledger and payment posting.

Customer: debit increases receivable. Credit decreases it.
Vendor: credit increases payable. Debit decreases it.
current_balance on the party row is a cache updated in the same transaction.
"""

from __future__ import annotations

from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from apps.customers.models import Customer
from apps.payments.models import LedgerEntry, LedgerEntryType, PartyType, Payment
from apps.vendors.models import Vendor


class LedgerService:
    """Single writer for party balances and append-only ledger rows."""

    def _lock_party(self, party_type: str, party_id: int):
        if party_type == PartyType.CUSTOMER:
            return Customer.objects.select_for_update().get(pk=party_id)
        return Vendor.objects.select_for_update().get(pk=party_id)

    def post(
        self,
        *,
        party_type: str,
        party_id: int,
        entry_type: str,
        debit: Decimal = Decimal("0"),
        credit: Decimal = Decimal("0"),
        reference_type: str = "",
        reference_id: str = "",
        notes: str = "",
        entry_date=None,
    ) -> LedgerEntry:
        party = self._lock_party(party_type, party_id)
        entry_date = entry_date or timezone.localdate()
        if party_type == PartyType.CUSTOMER:
            party.current_balance = party.current_balance + debit - credit
        else:
            party.current_balance = party.current_balance + credit - debit
        party.save(update_fields=["current_balance", "updated_at"])
        return LedgerEntry.objects.create(
            party_type=party_type,
            party_id=party_id,
            entry_date=entry_date,
            entry_type=entry_type,
            debit=debit,
            credit=credit,
            reference_type=reference_type,
            reference_id=str(reference_id),
            notes=notes,
        )

    def entries(self, party_type: str, party_id: int, date_from=None, date_to=None):
        qs = LedgerEntry.objects.filter(party_type=party_type, party_id=party_id)
        if date_from:
            qs = qs.filter(entry_date__gte=date_from)
        if date_to:
            qs = qs.filter(entry_date__lte=date_to)
        return qs


class PaymentService:
    """Customer receipts and supplier payments, always paired with a ledger row."""

    def create_payment(self, payload: dict) -> Payment:
        party_type = payload.get("party_type") or payload.get("party_type")
        method = payload.get("method") or payload.get("method") or "CASH"
        with transaction.atomic():
            payment = Payment.objects.create(
                party_type=party_type,
                party_id=payload.get("party_id") or payload.get("party_id"),
                payment_date=payload.get("payment_date") or payload.get("payment_date") or timezone.localdate(),
                amount=Decimal(str(payload["amount"])),
                method=method,
                reference=payload.get("reference", ""),
                notes=payload.get("notes", ""),
            )
            if payment.party_type == PartyType.CUSTOMER:
                ledger_service.post(
                    party_type=PartyType.CUSTOMER,
                    party_id=payment.party_id,
                    entry_type=LedgerEntryType.PAYMENT,
                    credit=payment.amount,
                    reference_type="payment",
                    reference_id=payment.id,
                    notes=payment.reference,
                    entry_date=payment.payment_date,
                )
            else:
                ledger_service.post(
                    party_type=PartyType.VENDOR,
                    party_id=payment.party_id,
                    entry_type=LedgerEntryType.PAYMENT,
                    debit=payment.amount,
                    reference_type="payment",
                    reference_id=payment.id,
                    notes=payment.reference,
                    entry_date=payment.payment_date,
                )
            return payment


ledger_service = LedgerService()
payment_service = PaymentService()
