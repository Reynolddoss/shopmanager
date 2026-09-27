"""Startup and on-demand SQLite / schema health for the desktop operator."""

from __future__ import annotations

from pathlib import Path

from django.conf import settings
from django.core.management import call_command
from django.db import connection
from django.db.migrations.executor import MigrationExecutor

from apps.core.backup import sqlite_integrity_service
from apps.core.paths import data_directory_service


CRITICAL_TABLES = (
    "core_applicationsettings",
    "products_product",
    "inventory_inventorybatch",
    "sales_sale",
    "purchases_purchase",
    "payments_payment",
)


class HealthService:
    """Never return Python tracebacks; return a recovery hint instead."""

    def diagnose(self) -> dict:
        db_path = Path(str(settings.DATABASES["default"]["NAME"]))
        integrity = "unknown"
        journal = "unknown"
        foreign_keys = "unknown"
        accessible = True
        ok = True
        try:
            with connection.cursor() as cursor:
                cursor.execute("PRAGMA integrity_check;")
                integrity = str(cursor.fetchone()[0])
                cursor.execute("PRAGMA journal_mode;")
                journal = str(cursor.fetchone()[0])
                cursor.execute("PRAGMA foreign_keys;")
                foreign_keys = str(cursor.fetchone()[0])
            ok = integrity == "ok"
        except Exception:
            accessible = db_path.exists()
            ok, integrity = (
                sqlite_integrity_service.integrity_ok(db_path) if accessible else (False, "inaccessible")
            )
        pending = self.pending_migrations()
        missing = self._missing_tables() if accessible and ok else list(CRITICAL_TABLES)
        status = "ok"
        recovery = ""
        if not accessible:
            status = "unusable"
            recovery = (
                "The shop database file is missing. Restore a backup from Settings, "
                "or reinstall without deleting AppData."
            )
        elif not ok:
            status = "unusable"
            recovery = (
                "SQLite reported corruption. Restore the latest validated backup. "
                "Do not keep using this file."
            )
        elif pending:
            status = "needs_upgrade"
            recovery = (
                "This copy is older than the application. Create a backup, then run the upgrade command."
            )
        elif missing:
            status = "unusable"
            recovery = "Required tables are missing. Restore a backup taken after a successful install."
        return {
            "status": status,
            "database": "sqlite",
            "integrity_check": integrity,
            "journal_mode": journal,
            "integrity_check": integrity,
            "journal_mode": journal,
            "foreign_keys": foreign_keys,
            "database_path": str(db_path),
            "backup_root": str(data_directory_service.backup_root()),
            "log_root": str(data_directory_service.log_root()),
            "pending_migrations": pending,
            "missing_tables": missing,
            "recovery_message": recovery,
            "application_version": getattr(settings, "APPLICATION_VERSION", "0.1.0"),
            "schema_version": pending[0] if pending else "current",
        }

    def pending_migrations(self) -> list[str]:
        try:
            executor = MigrationExecutor(connection)
            plan = executor.migration_plan(executor.loader.graph.leaf_nodes())
            return list(map(lambda item: f"{item[0].app_label}.{item[0].name}", plan))
        except Exception:
            return []

    def _missing_tables(self) -> list[str]:
        existing = set(connection.introspection.table_names())
        return list(filter(lambda name: name not in existing, CRITICAL_TABLES))

    def is_fresh_database(self) -> bool:
        """True before the first migrate (new install): nothing exists yet to back up."""
        return "django_migrations" not in set(connection.introspection.table_names())

    def apply_pending_migrations(self) -> None:
        """Used by the packaged launcher after an automatic pre-upgrade backup."""
        call_command("migrate", interactive=False, verbosity=0)


health_service = HealthService()
