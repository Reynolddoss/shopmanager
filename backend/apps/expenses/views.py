from rest_framework import viewsets

from apps.expenses.models import Expense, ExpenseCategory
from apps.expenses.serializers import ExpenseCategorySerializer, ExpenseSerializer


class ExpenseCategoryViewSet(viewsets.ModelViewSet):
    queryset = ExpenseCategory.objects.all()
    serializer_class = ExpenseCategorySerializer
    search_fields = ("name",)
    filterset_fields = ("is_active",)
    http_method_names = ["get", "post", "patch", "head", "options"]


class ExpenseViewSet(viewsets.ModelViewSet):
    queryset = Expense.objects.select_related("category").all()
    serializer_class = ExpenseSerializer
    search_fields = ("notes", "reference")
    filterset_fields = ("category", "payment_method")
    http_method_names = ["get", "post", "patch", "head", "options"]
