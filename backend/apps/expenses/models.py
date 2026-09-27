"""
Shop expenses. These are operating costs, not inventory purchases.

Purchases that create stock stay on Purchase. Expense rows never move inventory.
"""

from __future__ import annotations

from django.core.validators import MinValueValidator
from django.db import models

from apps.core.models import TimeStampedModel


class ExpenseCategory(TimeStampedModel):
    """Extensible expense labels: rent, salary, transport, utilities, other."""

    name = models.CharField(max_length=128, unique=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "expense categories"

    def __str__(self) -> str:
        return self.name


class Expense(TimeStampedModel):
    """One paid shop expense. Date + category + amount are the analytics grain."""

    category = models.ForeignKey(ExpenseCategory, on_delete=models.PROTECT, related_name="expenses")
    expense_date = models.DateField(db_index=True)
    amount = models.DecimalField(max_digits=14, decimal_places=2, validators=[MinValueValidator(0)])
    payment_method = models.CharField(max_length=16, default="CASH")
    notes = models.TextField(blank=True, default="")
    reference = models.CharField(max_length=64, blank=True, default="")

    class Meta:
        ordering = ["-expense_date", "-id"]
        indexes = [models.Index(fields=["expense_date", "category"])]

    def __str__(self) -> str:
        return f"{self.expense_date} {self.category_id} {self.amount}"
