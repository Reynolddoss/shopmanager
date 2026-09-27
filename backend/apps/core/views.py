"""Thin API views for health, version, and shop settings."""

from __future__ import annotations

from django.conf import settings
from django.db import connection
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from rest_framework.permissions import AllowAny

from apps.core.backup import snapshot_backup_service
from apps.core.health import health_service
from apps.core.printing import invoice_print_service
from apps.core.serializers import ApplicationSettingsSerializer
from apps.core.services import settings_service
from apps.sales.models import Sale
from apps.sales.services import invoice_payload_service


class HealthView(APIView):
    """Confirm the process is up and SQLite accepts a pragma query."""

    permission_classes = [AllowAny]

    def get(self, request: Request) -> Response:
        payload = health_service.diagnose()
        payload["integrity_check"] = payload.get("integrity_check", "")
        payload["journal_mode"] = payload.get("journal_mode", "")
        if payload.get("status") == "ok":
            payload["status"] = "ok"
        return Response(payload)


class VersionView(APIView):
    """Report application and API versions for the desktop shell."""

    permission_classes = [AllowAny]

    def get(self, request: Request) -> Response:
        return Response(
            {
                "name": getattr(settings, "APPLICATION_NAME", settings.APPLICATION_NAME),
                "version": getattr(settings, "APPLICATION_VERSION", settings.APPLICATION_VERSION),
                "api": getattr(settings, "API_VERSION", settings.API_VERSION),
            }
        )


class BackupListCreateView(APIView):
    """List timestamped snapshots or create a new validated backup."""

    def get(self, request: Request) -> Response:
        snapshot_backup_service.maybe_run_schedule()
        return Response({"results": snapshot_backup_service.list_snapshots()})

    def post(self, request: Request) -> Response:
        reason = request.data.get("reason") or "manual"
        return Response(snapshot_backup_service.create_snapshot(reason=reason), status=201)


class BackupRestoreView(APIView):
    """Restore a named snapshot after an explicit confirm flag."""

    def post(self, request: Request) -> Response:
        folder = request.data.get("folder") or ""
        confirm = bool(request.data.get("confirm"))
        return Response(snapshot_backup_service.restore_snapshot(folder, confirm=confirm))


class InvoicePrintView(APIView):
    """Return printer-neutral HTML for A4 or thermal layouts."""

    def get(self, request: Request, pk: int) -> Response:
        sale = Sale.objects.get(pk=pk)
        kind = request.query_params.get("kind") or "a4"
        html = invoice_print_service.render(invoice_payload_service.for_sale(sale), kind=kind)
        return Response({"html": html, "kind": kind})


class SettingsView(APIView):
    """Read or update the singleton shop configuration."""

    def get(self, request: Request) -> Response:
        instance = settings_service.get_or_create()
        return Response(ApplicationSettingsSerializer(instance).data)

    def patch(self, request: Request) -> Response:
        instance = settings_service.get_or_create()
        serializer = ApplicationSettingsSerializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)
