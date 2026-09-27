"""
Invoice and bill numbers are allocated only on the server.

The desktop UI may display the next number after save; it must never invent one.
"""

from __future__ import annotations

from datetime import date

from django.db import transaction

from apps.core.models import ApplicationSettings, DocumentSequence


class DocumentNumberService:
    """Allocate unique, prefix+year+sequence document numbers."""

    def financial_year(self, on: date | None = None) -> str:
        """Indian FY label, e.g. 2026-27 for dates from Apr 2026."""
        day = on or date.today()
        start = day.year if day.month >= 4 else day.year - 1
        return f"{start}-{str(start + 1)[-2:]}"

    @transaction.atomic
    def next_number(self, document_type: str, *, on: date | None = None, prefix: str | None = None) -> str:
        """Return the next number and persist the increment."""
        year = self.financial_year(on)
        settings_row = ApplicationSettings.objects.filter(singleton_key=1).first()
        default_prefix = prefix
        if default_prefix is None:
            if document_type == "SALE":
                default_prefix = settings_row.sale_invoice_prefix if settings_row else "MM"
            elif document_type == "PURCHASE":
                default_prefix = settings_row.purchase_invoice_prefix if settings_row else "PUR"
            else:
                default_prefix = document_type[:3]
        seq, _created = DocumentSequence.objects.select_for_update().get_or_create(
            document_type=document_type,
            financial_year=year,
            defaults={"prefix": default_prefix, "next_value": 1},
        )
        number = f"{seq.prefix}-{year}-{seq.next_value:05d}"
        seq.next_value += 1
        seq.save(update_fields=["next_value"])
        return number


document_number_service = DocumentNumberService()
