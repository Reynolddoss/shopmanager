"""
SQLite-first backup and restore.

CSV files are a portable extra copy. They are not used to rebuild ledgers.
Restore always copies a validated SQLite file after a safety snapshot of the live DB.
"""

from __future__ import annotations

import csv
import hashlib
import json
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from django.apps import apps
from django.conf import settings
from django.db import connection
from django.db.migrations.recorder import MigrationRecorder
from django.utils import timezone as django_timezone

from apps.core.models import ApplicationSettings, AuditLog
from apps.core.paths import data_directory_service


class SqliteIntegrityService:
    """Run SQLite PRAGMA checks without going through Django's query compiler."""

    def integrity_ok(self, db_path: Path) -> tuple[bool, str]:
        if not db_path.is_file() or db_path.stat().st_size == 0:
            return False, "missing_or_empty"
        conn = sqlite3.connect(str(db_path))
        try:
            row = conn.execute("PRAGMA integrity_check;").fetchone()
            result = row[0] if row else "unknown"
            return result == "ok", str(result)
        finally:
            conn.close()

    def sha256(self, db_path: Path) -> str:
        digest = hashlib.sha256()
        with db_path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()


class SnapshotBackupService:
    """
    One timestamped folder per backup:

    backups/<stamp>/database/mm_electricals.sqlite3
    backups/<stamp>/csv/*.csv
    backups/<stamp>/metadata.json
    """

    CSV_MODELS = (
        ("products", "Product"),
        ("products", "Category"),
        ("products", "Brand"),
        ("vendors", "Vendor"),
        ("customers", "Customer"),
        ("purchases", "Purchase"),
        ("purchases", "PurchaseItem"),
        ("sales", "Sale"),
        ("sales", "SaleItem"),
        ("payments", "Payment"),
        ("expenses", "Expense"),
        ("inventory", "StockMovement"),
        ("inventory", "InventoryBatch"),
    )

    def __init__(self) -> None:
        self.integrity = SqliteIntegrityService()
        self.backup_root = data_directory_service.backup_root()

    def create_snapshot(self, *, reason: str = "manual") -> dict[str, Any]:
        """Copy SQLite via the backup API, export CSV, write metadata, prune old folders."""
        stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H%M%S_%f")
        folder = self.backup_root / stamp
        db_dir = folder / "database"
        csv_dir = folder / "csv"
        db_dir.mkdir(parents=True, exist_ok=True)
        csv_dir.mkdir(parents=True, exist_ok=True)
        live = Path(str(settings.DATABASES["default"]["NAME"]))
        dest = db_dir / "mm_electricals.sqlite3"
        if dest.exists():
            dest.unlink()
        quoted = str(dest.resolve()).replace("'", "''")
        with connection.cursor() as cursor:
            cursor.execute(f"VACUUM INTO '{quoted}'")
        ok, message = self.integrity.integrity_ok(dest)
        if not ok:
            raise ValueError(f"Backup failed integrity check: {message}")
        self._export_csv(csv_dir)
        metadata = {
            "created_at": datetime.now(timezone.utc).isoformat(),
            "reason": reason,
            "application_version": getattr(settings, "APPLICATION_VERSION", "0.1.0"),
            "schema_version": self._schema_version(),
            "sqlite_sha256": self.integrity.sha256(dest),
            "integrity_check": message,
            "live_database": str(live),
        }
        (folder / "metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
        self._record_audit("backup_create", stamp, metadata)
        self.prune()
        return {"folder": stamp, "path": str(folder), "metadata": metadata}

    def list_snapshots(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        if not self.backup_root.exists():
            return rows
        for folder in sorted(self.backup_root.iterdir(), reverse=True):
            meta = folder / "metadata.json"
            if folder.is_dir() and meta.is_file():
                payload = json.loads(meta.read_text(encoding="utf-8"))
                payload["folder"] = folder.name
                rows.append(payload)
        return rows

    def restore_snapshot(self, folder_name: str, *, confirm: bool) -> dict[str, Any]:
        """
        Validate backup, snapshot the live file, copy backup over live, re-check.

        If the copy fails integrity, the pre-restore safety file is copied back.
        """
        if not confirm:
            raise ValueError("Restore requires confirm=true.")
        folder = data_directory_service.safe_child(folder_name)
        backup_db = folder / "database" / "mm_electricals.sqlite3"
        ok, message = self.integrity.integrity_ok(backup_db)
        if not ok:
            raise ValueError(f"Backup is not usable: {message}")
        live = Path(str(settings.DATABASES["default"]["NAME"]))
        safety = self.create_snapshot(reason="pre_restore_safety")
        safety_db = data_directory_service.safe_child(safety["folder"]) / "database" / "mm_electricals.sqlite3"
        connection.close()
        try:
            shutil.copy2(backup_db, live)
            ok_after, after_msg = self.integrity.integrity_ok(live)
            if not ok_after:
                raise ValueError(f"Restored file failed integrity: {after_msg}")
        except Exception:
            shutil.copy2(safety_db, live)
            raise
        self._record_audit("backup_restore", folder_name, {"safety_folder": safety["folder"]})
        return {"restored": folder_name, "safety_folder": safety["folder"], "integrity_check": "ok"}

    def prune(self) -> None:
        retention = int(
            ApplicationSettings.objects.filter(singleton_key=1)
            .values_list("backup_retention_count", flat=True)
            .first()
            or getattr(settings, "BACKUP_RETENTION_COUNT", 14)
        )
        folders = list(
            filter(
                lambda item: item.is_dir() and (item / "metadata.json").is_file(),
                sorted(self.backup_root.iterdir(), key=lambda item: item.name, reverse=True),
            )
        )
        list(map(lambda stale: shutil.rmtree(stale, ignore_errors=True), folders[retention:]))

    def maybe_run_schedule(self) -> dict[str, Any] | None:
        """Run a backup when scheduled backups are enabled and the last one is stale."""
        row = ApplicationSettings.objects.filter(singleton_key=1).first()
        if row is None or not row.scheduled_backup_enabled:
            return None
        extra = row.extra if isinstance(row.extra, dict) else {}
        last = extra.get("last_backup_at")
        frequency = extra.get("backup_frequency", "daily")
        now = django_timezone.now()
        if last:
            last_dt = datetime.fromisoformat(str(last).replace("Z", "+00:00"))
            if last_dt.tzinfo is None:
                last_dt = last_dt.replace(tzinfo=timezone.utc)
            hours = 24 if frequency != "weekly" else 24 * 7
            if (now - last_dt).total_seconds() < hours * 3600:
                return None
        snapshot = self.create_snapshot(reason=f"scheduled_{frequency}")
        extra["last_backup_at"] = now.isoformat()
        row.extra = extra
        row.save(update_fields=["extra", "updated_at"])
        return snapshot

    def _export_csv(self, csv_dir: Path) -> None:
        for app_label, model_name in self.CSV_MODELS:
            try:
                model = apps.get_model(app_label, model_name)
            except LookupError:
                continue
            path = csv_dir / f"{app_label}_{model_name.lower()}.csv"
            rows = list(model.objects.all().values())
            with path.open("w", newline="", encoding="utf-8") as handle:
                if not rows:
                    handle.write("")
                    continue
                writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
                writer.writeheader()
                list(map(lambda row: writer.writerow(self._stringify(row)), rows))

    def _stringify(self, row: dict[str, Any]) -> dict[str, Any]:
        return dict(map(lambda item: (item[0], "" if item[1] is None else str(item[1])), row.items()))

    def _schema_version(self) -> str:
        latest = MigrationRecorder.Migration.objects.order_by("-id").values_list("app", "name").first()
        if not latest:
            return "empty"
        return f"{latest[0]}.{latest[1]}"

    def _record_audit(self, action: str, entity_id: str, payload: dict) -> None:
        AuditLog.objects.create(
            action=action,
            entity="backup",
            entity_id=entity_id,
            new_data=payload,
            source="backup",
            actor="system",
        )


snapshot_backup_service = SnapshotBackupService()
sqlite_integrity_service = SqliteIntegrityService()
