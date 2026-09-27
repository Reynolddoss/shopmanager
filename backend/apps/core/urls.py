"""Core API routes: health, version, settings."""

from django.urls import path

from apps.core.auth_views import AuthLoginView, AuthLogoutView, AuthRegisterView, AuthStatusView
from apps.core.views import (
    BackupListCreateView,
    BackupRestoreView,
    HealthView,
    InvoicePrintView,
    SettingsView,
    VersionView,
)

urlpatterns = [
    path("auth/status/", AuthStatusView.as_view(), name="auth-status"),
    path("auth/register/", AuthRegisterView.as_view(), name="auth-register"),
    path("auth/login/", AuthLoginView.as_view(), name="auth-login"),
    path("auth/logout/", AuthLogoutView.as_view(), name="auth-logout"),
    path("health/", HealthView.as_view(), name="api-health"),
    path("version/", VersionView.as_view(), name="api-version"),
    path("settings/", SettingsView.as_view(), name="api-settings"),
    path("backups/", BackupListCreateView.as_view(), name="api-backups"),
    path("backups/restore/", BackupRestoreView.as_view(), name="api-backup-restore"),
    path("sales/<int:pk>/print/", InvoicePrintView.as_view(), name="api-sale-print"),
]
