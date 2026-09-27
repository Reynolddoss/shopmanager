from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.purchases.models import Purchase, PurchaseReturn
from apps.purchases.serializers import (
    PurchaseListSerializer,
    PurchaseReturnSerializer,
    PurchaseSerializer,
    PurchaseWriteSerializer,
)
from apps.purchases.services import purchase_service


class PurchaseViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    queryset = Purchase.objects.select_related("vendor").prefetch_related("items").all()
    serializer_class = PurchaseSerializer
    search_fields = ("bill_number", "vendor__name")
    filterset_fields = {
        "payment_method": ["exact"],
        "is_cancelled": ["exact"],
        "bill_date": ["exact", "gte", "lte"],
    }
    http_method_names = ["get", "post", "head", "options"]

    def get_serializer_class(self):
        if self.action == "list":
            return PurchaseListSerializer
        return PurchaseSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params
        date_from = params.get("date_from")
        date_to = params.get("date_to")
        if date_from:
            qs = qs.filter(bill_date__gte=date_from)
        if date_to:
            qs = qs.filter(bill_date__lte=date_to)
        return qs

    def create(self, request):
        writer = PurchaseWriteSerializer(data=request.data)
        writer.is_valid(raise_exception=True)
        purchase = purchase_service.create_purchase(writer.validated_data)
        return Response(PurchaseSerializer(purchase).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path="returns")
    def create_return(self, request, pk=None):
        purchase = self.get_object()
        ret = purchase_service.create_return(
            purchase,
            request.data.get("items") or [],
            notes=request.data.get("notes", ""),
        )
        return Response(PurchaseReturnSerializer(ret).data, status=status.HTTP_201_CREATED)


class PurchaseReturnViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    queryset = PurchaseReturn.objects.select_related("purchase").prefetch_related("items").all()
    serializer_class = PurchaseReturnSerializer
    http_method_names = ["get", "head", "options"]
