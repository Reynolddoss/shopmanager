from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.sales.models import Sale, SaleReturn
from apps.sales.serializers import SaleListSerializer, SaleReturnSerializer, SaleSerializer, SaleWriteSerializer
from apps.sales.services import invoice_payload_service, sale_service


class SaleViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    queryset = Sale.objects.select_related("customer").prefetch_related("items").all()
    serializer_class = SaleSerializer
    search_fields = ("invoice_number", "customer__name", "customer__phone", "payment_reference")
    filterset_fields = {
        "payment_method": ["exact"],
        "payment_status": ["exact"],
        "is_cancelled": ["exact"],
        "invoice_date": ["exact", "gte", "lte"],
    }
    http_method_names = ["get", "post", "head", "options"]

    def get_serializer_class(self):
        if self.action == "list":
            return SaleListSerializer
        return SaleSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        # Extra date aliases used by the History screen.
        params = self.request.query_params
        date_from = params.get("date_from")
        date_to = params.get("date_to")
        if date_from:
            qs = qs.filter(invoice_date__gte=date_from)
        if date_to:
            qs = qs.filter(invoice_date__lte=date_to)
        return qs

    def create(self, request):
        writer = SaleWriteSerializer(data=request.data)
        writer.is_valid(raise_exception=True)
        sale = sale_service.create_sale(writer.validated_data)
        return Response(SaleSerializer(sale).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path="revise")
    def revise(self, request, pk=None):
        """Replace items/payment on an existing invoice (same number)."""
        sale = self.get_object()
        writer = SaleWriteSerializer(data=request.data)
        writer.is_valid(raise_exception=True)
        revised = sale_service.revise_sale(sale, writer.validated_data)
        return Response(SaleSerializer(revised).data)

    @action(detail=True, methods=["get"], url_path="invoice")
    def invoice(self, request, pk=None):
        sale = self.get_object()
        return Response(invoice_payload_service.for_sale(sale))

    @action(detail=True, methods=["post"], url_path="returns")
    def create_return(self, request, pk=None):
        sale = self.get_object()
        ret = sale_service.create_return(
            sale,
            request.data.get("items") or [],
            notes=request.data.get("notes", ""),
        )
        return Response(SaleReturnSerializer(ret).data, status=status.HTTP_201_CREATED)


class SaleReturnViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    queryset = SaleReturn.objects.select_related("sale").prefetch_related("items").all()
    serializer_class = SaleReturnSerializer
    http_method_names = ["get", "head", "options"]
