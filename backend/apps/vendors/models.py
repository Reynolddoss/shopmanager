"""Permanent vendor (supplier) master records."""

from __future__ import annotations

from django.db import models

from apps.core.models import TimeStampedModel


class Vendor(TimeStampedModel):
    """
    Supplier used on purchases and reporting.

    Never reduce a vendor to a free-text name on an invoice. Inactive vendors
    remain in the database so historical purchases stay meaningful.
    """

    name = models.CharField(max_length=255, unique=True, db_index=True)
    phone = models.CharField(max_length=32, blank=True, default="")
    alternate_phone = models.CharField(max_length=32, blank=True, default="")
    email = models.EmailField(blank=True, default="")
    address = models.TextField(blank=True, default="")
    gstin = models.CharField(max_length=32, blank=True, default="")
    contact_person = models.CharField(max_length=128, blank=True, default="")
    payment_terms = models.CharField(max_length=255, blank=True, default="")
    opening_balance = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    current_balance = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    notes = models.TextField(blank=True, default="")
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name
