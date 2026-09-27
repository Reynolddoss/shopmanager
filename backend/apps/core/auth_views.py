"""Session auth endpoints: register shop, login, logout, status."""

from __future__ import annotations

from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.auth_serializers import LoginSerializer, RegisterSerializer
from apps.core.auth_service import auth_service
from apps.core.authentication import CsrfExemptSessionAuthentication
from apps.core.permissions import AllowRegisterOnlyIfNew, IsAuthenticatedShopUser


class AuthBaseView(APIView):
    authentication_classes = [CsrfExemptSessionAuthentication]


class AuthStatusView(AuthBaseView):
    """Tell the UI whether to show registration, login, or the main app."""

    permission_classes = [AllowAny]

    def get(self, request: Request) -> Response:
        return Response(auth_service.status(request))


class AuthRegisterView(AuthBaseView):
    """First-run setup: shop details + owner username/password."""

    permission_classes = [AllowRegisterOnlyIfNew]

    def post(self, request: Request) -> Response:
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = auth_service.register(request, serializer.validated_data)
        return Response(payload, status=201)


class AuthLoginView(AuthBaseView):
    permission_classes = [AllowAny]

    def post(self, request: Request) -> Response:
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = auth_service.login(request, serializer.validated_data["user"])
        return Response(payload)


class AuthLogoutView(AuthBaseView):
    permission_classes = [IsAuthenticatedShopUser]

    def post(self, request: Request) -> Response:
        return Response(auth_service.logout(request))
