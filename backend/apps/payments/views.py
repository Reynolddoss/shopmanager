from rest_framework import mixins, status, viewsets
from rest_framework.response import Response

from apps.payments.models import Payment
from apps.payments.serializers import PaymentSerializer
from apps.payments.services import payment_service


class PaymentViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    queryset = Payment.objects.all()
    serializer_class = PaymentSerializer
    filterset_fields = ("party_type", "party_id", "method")
    http_method_names = ["get", "post", "head", "options"]

    def create(self, request):
        payment = payment_service.create_payment(request.data)
        return Response(PaymentSerializer(payment).data, status=status.HTTP_201_CREATED)
