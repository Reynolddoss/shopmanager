from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.response import Response

from apps.customers.models import Customer, CustomerType
from apps.customers.serializers import CustomerSerializer, CustomerTypeSerializer
from apps.customers.services import customer_phone_service, customer_type_seed_service
from apps.payments.models import PartyType
from apps.payments.serializers import LedgerEntrySerializer
from apps.payments.services import ledger_service


class CustomerTypeViewSet(viewsets.ModelViewSet):
    queryset = CustomerType.objects.all()
    serializer_class = CustomerTypeSerializer
    search_fields = ("name", "code")
    filterset_fields = ("is_active",)
    http_method_names = ["get", "post", "patch", "head", "options"]

    def list(self, request: Request, *args, **kwargs):
        customer_type_seed_service.ensure_defaults()
        return super().list(request, *args, **kwargs)


class CustomerViewSet(viewsets.ModelViewSet):
    queryset = Customer.objects.select_related("customer_type").all()
    serializer_class = CustomerSerializer
    search_fields = ("name", "phone", "alternate_phone", "gstin", "notes")
    filterset_fields = ("is_active", "customer_type")
    http_method_names = ["get", "post", "patch", "head", "options"]

    def list(self, request: Request, *args, **kwargs):
        customer_type_seed_service.ensure_defaults()
        return super().list(request, *args, **kwargs)

    @action(detail=False, methods=["get"], url_path="lookup")
    def lookup(self, request: Request) -> Response:
        """
        Find customers by mobile or name fragment for billing linkage.

        Query: ?q=98765… or ?phone=98765…
        """
        customer_type_seed_service.ensure_defaults()
        q = (request.query_params.get("q") or request.query_params.get("phone") or "").strip()
        if not q:
            return Response([])
        rows = customer_phone_service.matches_queryset(q)[:25]
        return Response(CustomerSerializer(rows, many=True).data)

    @action(detail=True, methods=["get"])
    def ledger(self, request, pk=None):
        customer = self.get_object()
        entries = ledger_service.entries(
            PartyType.CUSTOMER,
            customer.id,
            date_from=request.query_params.get("date_from"),
            date_to=request.query_params.get("date_to"),
        )
        return Response(
            {
                "opening_balance": str(customer.opening_balance),
                "current_balance": str(customer.current_balance),
                "entries": LedgerEntrySerializer(entries, many=True).data,
            }
        )
