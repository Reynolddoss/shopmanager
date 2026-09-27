from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.payments.models import PartyType
from apps.payments.serializers import LedgerEntrySerializer
from apps.payments.services import ledger_service
from apps.purchases.models import Purchase
from apps.purchases.serializers import PurchaseSerializer
from apps.vendors.models import Vendor
from apps.vendors.serializers import VendorSerializer


class VendorViewSet(viewsets.ModelViewSet):
    queryset = Vendor.objects.all()
    serializer_class = VendorSerializer
    search_fields = ("name", "phone", "gstin", "contact_person")
    filterset_fields = ("is_active",)
    http_method_names = ["get", "post", "patch", "head", "options"]

    @action(detail=True, methods=["get"])
    def ledger(self, request, pk=None):
        vendor = self.get_object()
        entries = ledger_service.entries(
            PartyType.VENDOR,
            vendor.id,
            date_from=request.query_params.get("date_from"),
            date_to=request.query_params.get("date_to"),
        )
        return Response(
            {
                "opening_balance": str(vendor.opening_balance),
                "current_balance": str(vendor.current_balance),
                "entries": LedgerEntrySerializer(entries, many=True).data,
            }
        )

    @action(detail=True, methods=["get"])
    def purchases(self, request, pk=None):
        vendor = self.get_object()
        qs = Purchase.objects.filter(vendor=vendor).prefetch_related("items")
        return Response(PurchaseSerializer(qs, many=True).data)
