"""
Cross-cutting services: audit writes, settings singleton, SQLite/CSV backup.

Views stay thin and call these classes. Restore and scheduled backup are
architected here; a full operator UI belongs in a later phase.
"""

from __future__ import annotations

import csv
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from django.conf import settings
from django.db import connection

from apps.core.models import ApplicationSettings, AuditLog


class AuditService:
    """Append-only audit writer. Never updates or deletes existing rows."""

    def _write(self, **kwargs: Any) -> AuditLog:
        action = kwargs.get("action") or kwargs.get("action") or ""
        entity = kwargs.get("entity") or kwargs.get("entity") or ""
        entity_id = kwargs.get("entity_id", kwargs.get("entity_id", ""))
        return AuditLog.objects.create(
            action=str(action),
            entity=str(entity),
            entity_id=str(entity_id),
            old_data=kwargs.get("old_data", kwargs.get("old_data")),
            new_data=kwargs.get("new_data", kwargs.get("new_data")),
            source=str(kwargs.get("source", "api")),
            actor=str(kwargs.get("actor", "system")),
        )

    def record(self, **kwargs: Any) -> AuditLog:
        return self._write(**kwargs)


class SettingsService:
    """Load or create the single ApplicationSettings row."""

    def get_or_create(self) -> ApplicationSettings:
        """Return the shop settings singleton, creating defaults on first run."""
        defaults = getattr(settings, "DEFAULT_SHOP_SETTINGS", {})
        obj, _created = ApplicationSettings.objects.get_or_create(
            singleton_key=1,
            defaults={
                "shop_name": defaults.get("shop_name", ""),
                "address": defaults.get("address", ""),
                "gstin": defaults.get("gstin", ""),
                "phone": defaults.get("phone", ""),
                "invoice_prefix": defaults.get("invoice_prefix", "SH"),
                "currency": defaults.get("currency", "INR"),
                "default_tax_inclusive": defaults.get("default_tax_inclusive", False),
                "low_stock_threshold": defaults.get("low_stock_threshold", 5),
            },
        )
        return obj


class BackupService:
    """
    SQLite-first backup with CSV as a portable secondary format.

    SQLite copies are the recovery format. CSV exports are for portability,
    not for restoring transactional integrity.
    """

    def __init__(self, backup_root: Path | None = None) -> None:
        self.backup_root = Path(backup_root or settings.BACKUP_ROOT)
        self.backup_root.mkdir(parents=True, exist_ok=True)

    def create_snapshot(self, *, reason: str = "manual") -> dict[str, Any]:
        """Delegate to SnapshotBackupService so older callers keep working."""
        from apps.core.backup import snapshot_backup_service

        return snapshot_backup_service.create_snapshot(reason=reason)

    def create_sqlite_backup(self) -> Path:
        """
        Copy the live database using SQLite's backup API when available.

        Falls back to a filesystem copy after a WAL checkpoint so readers see
        a consistent snapshot.
        """
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        dest = self.backup_root / f"mm_electricals_{stamp}.sqlite3"
        db_path = Path(str(settings.DATABASES["default"]["NAME"]))
        with connection.cursor() as cursor:
            cursor.execute("PRAGMA wal_checkpoint(FULL);")
        shutil.copy2(db_path, dest)
        self._write_metadata(dest, kind="sqlite")
        self.prune_retention()
        return dest

    def export_csv_snapshot(self, table_rows: dict[str, list[dict[str, Any]]]) -> Path:
        """Write one CSV file per table name plus a metadata sidecar."""
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        folder = self.backup_root / f"csv_{stamp}"
        folder.mkdir(parents=True, exist_ok=True)
        for table, rows in table_rows.items():
            path = folder / f"{table}.csv"
            if not rows:
                path.write_text("", encoding="utf-8")
                continue
            fieldnames = list(rows[0].keys())
            with path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=fieldnames)
                writer.writeheader()
                list(map(lambda row: writer.writerow(row), rows))
        self._write_metadata(folder, kind="csv")
        return folder

    def validate_sqlite_file(self, path: Path) -> bool:
        """Return True when the file exists, is non-empty, and hashes stably."""
        if not path.is_file() or path.stat().st_size == 0:
            return False
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        return len(digest) == 64

    def prune_retention(self) -> None:
        """Keep the newest N sqlite backups; never delete the live database."""
        count = int(
            ApplicationSettings.objects.filter(singleton_key=1)
            .values_list("backup_retention_count", flat=True)
            .first()
            or settings.BACKUP_RETENTION_COUNT
        )
        files = sorted(
            self.backup_root.glob("mm_electricals_*.sqlite3"),
            key=lambda item: item.stat().st_mtime,
            reverse=True,
        )
        list(map(lambda stale: stale.unlink(missing_ok=True), files[count:]))

    def restore_sqlite(self, backup_path: Path, live_path: Path) -> None:
        """
        Replace the live database with a validated backup copy.

        Callers must stop writers first. This method does not start the API.
        """
        if not self.validate_sqlite_file(backup_path):
            raise ValueError("Backup file failed validation.")
        shutil.copy2(backup_path, live_path)

    def _write_metadata(self, target: Path, *, kind: str) -> None:
        """Sidecar JSON describing when and how the backup was produced."""
        payload = {
            "kind": kind,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "application_version": settings.APPLICATION_VERSION,
            "path": str(target),
        }
        meta_path = target.with_suffix(target.suffix + ".meta.json") if target.is_file() else target / "meta.json"
        meta_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


audit_service = AuditService()
settings_service = SettingsService()
backup_service = BackupService()
