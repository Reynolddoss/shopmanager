"""Expense serializers. Amounts are stored as posted; React does not recompute totals."""

from __future__ import annotations

from rest_framework import serializers

from apps.expenses.models import Expense, ExpenseCategory


class ExpenseCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ExpenseCategory
        fields = ("id", "name", "is_active", "created_at", "updated_at")
        read_only_fields = ("id", "created_at", "updated_at")


class ExpenseSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source="category.name", read_only=True)

    class Meta:
        model = Expense
        fields = (
            "id",
            "category",
            "category_name",
            "expense_date",
            "amount",
            "payment_method",
            "notes",
            "reference",
            "created_at",
        )
        read_only_fields = ("id", "created_at")
