"""
Party ledgers and cash-bank receipts/payments.

Balances are derived from ledger rows. Customer.current_balance and
Vendor.current_balance are caches updated in the same transaction.
"""

from __future__ import annotations

from django.core.validators import MinValueValidator
from django.db import models

from apps.core.models import TimeStampedModel


class PartyType(models.TextChoices):
    CUSTOMER = "CUSTOMER", "Customer"
    VENDOR = "VENDOR", "Vendor"


class LedgerEntryType(models.TextChoices):
    OPENING = "OPENING", "Opening balance"
    SALE = "SALE", "Sale"
    PURCHASE = "PURCHASE", "Purchase"
    PAYMENT = "PAYMENT", "Payment"
    SALE_RETURN = "SALE_RETURN", "Sale return"
    PURCHASE_RETURN = "PURCHASE_RETURN", "Purchase return"
    ADJUSTMENT = "ADJUSTMENT", "Adjustment"


class PaymentMethod(models.TextChoices):
    CASH = "CASH", "Cash"
    UPI = "UPI", "UPI"
    CARD = "CARD", "Card"
    BANK = "BANK", "Bank transfer"
    CREDIT = "CREDIT", "Credit"
    MIXED = "MIXED", "Partial / mixed"


class LedgerEntry(TimeStampedModel):
    """
    Append-only party ledger.

    Customer: debit increases what they owe us. Credit decreases it.
    Vendor: credit increases what we owe them. Debit decreases it.
    """

    party_type = models.CharField(max_length=16, choices=PartyType.choices, db_index=True)
    party_id = models.PositiveIntegerField(db_index=True)
    entry_date = models.DateField(db_index=True)
    entry_type = models.CharField(max_length=32, choices=LedgerEntryType.choices)
    debit = models.DecimalField(max_digits=14, decimal_places=2, default=0, validators=[MinValueValidator(0)])
    credit = models.DecimalField(max_digits=14, decimal_places=2, default=0, validators=[MinValueValidator(0)])
    reference_type = models.CharField(max_length=64, blank=True, default="")
    reference_id = models.CharField(max_length=64, blank=True, default="")
    notes = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["entry_date", "id"]
        indexes = [models.Index(fields=["party_type", "party_id", "entry_date"])]


class Payment(TimeStampedModel):
    """Customer receipt or supplier payment. Always paired with a ledger row."""

    party_type = models.CharField(max_length=16, choices=PartyType.choices, db_index=True)
    party_id = models.PositiveIntegerField(db_index=True)
    payment_date = models.DateField(db_index=True)
    amount = models.DecimalField(max_digits=14, decimal_places=2, validators=[MinValueValidator(0)])
    method = models.CharField(max_length=16, choices=PaymentMethod.choices, default=PaymentMethod.CASH)
    reference = models.CharField(max_length=64, blank=True, default="")
    notes = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["-payment_date", "-id"]
