"""Permanent customer master records with extensible customer types."""

from __future__ import annotations

from django.core.validators import MinValueValidator
from django.db import models

from apps.core.models import TimeStampedModel


class CustomerType(TimeStampedModel):
    """
    Extensible classification: Retail, Electrician, Contractor, Builder, Wholesale, Other.

    New types are rows, not a hardcoded enum, so the shop can add labels later.
    """

    code = models.SlugField(max_length=32, unique=True)
    name = models.CharField(max_length=64, unique=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class Customer(TimeStampedModel):
    """
    Party who buys from the shop.

    Opening balance and credit limit are stored here; invoices will reference
    this row rather than copying a name onto each bill.
    """

    name = models.CharField(max_length=255, db_index=True)
    phone = models.CharField(max_length=32, blank=True, default="", db_index=True)
    alternate_phone = models.CharField(max_length=32, blank=True, default="")
    address = models.TextField(blank=True, default="")
    gstin = models.CharField(max_length=32, blank=True, default="")
    customer_type = models.ForeignKey(
        CustomerType,
        on_delete=models.PROTECT,
        related_name="customers",
        null=True,
        blank=True,
    )
    credit_limit = models.DecimalField(
        max_digits=12, decimal_places=2, default=0, validators=[MinValueValidator(0)]
    )
    opening_balance = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    current_balance = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    notes = models.TextField(blank=True, default="")
    # Reserved for a later loyalty programme; not awarded by sales yet.
    loyalty_points = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name
