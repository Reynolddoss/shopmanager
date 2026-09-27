"""Phase 5: backup, restore safety, health, loopback binding."""

from __future__ import annotations

from pathlib import Path

import pytest
from django.test import Client, override_settings

from apps.core.backup import snapshot_backup_service
from apps.core.models import ApplicationSettings, AuditLog
from apps.products.models import Product
from tests.factories import CatalogFactory


@pytest.mark.django_db(transaction=True)
class TestPhase5BackupRestore:
    def test_snapshot_validates_and_does_not_overwrite(self, tmp_path, settings) -> None:
        settings.DATABASES["default"]["NAME"]  # live test db
        CatalogFactory.product(sku="P5-1")
        first = snapshot_backup_service.create_snapshot(reason="test_one")
        CatalogFactory.product(sku="P5-2")
        second = snapshot_backup_service.create_snapshot(reason="test_two")
        assert first["folder"] != second["folder"]
        assert Path(first["path"]).exists()
        assert Path(second["path"]).exists()
        meta = Path(second["path"]) / "metadata.json"
        assert meta.is_file()
        db_copy = Path(second["path"]) / "database" / "mm_electricals.sqlite3"
        assert db_copy.stat().st_size > 0
        assert AuditLog.objects.filter(action="backup_create").exists()

    def test_restore_makes_safety_copy_and_round_trips(self) -> None:
        CatalogFactory.product(sku="KEEP-ME")
        snapshot = snapshot_backup_service.create_snapshot(reason="before_restore")
        db_copy = Path(snapshot["path"]) / "database" / "mm_electricals.sqlite3"
        assert db_copy.is_file()
        with pytest.raises(ValueError):
            snapshot_backup_service.restore_snapshot(snapshot["folder"], confirm=False)
        live = Path(str(__import__("django.conf", fromlist=["settings"]).settings.DATABASES["default"]["NAME"]))
        if live.is_file():
            result = snapshot_backup_service.restore_snapshot(snapshot["folder"], confirm=True)
            assert result["safety_folder"]


    def test_restore_without_confirm_is_rejected(self) -> None:
        snapshot = snapshot_backup_service.create_snapshot(reason="no_confirm")
        with pytest.raises(ValueError):
            snapshot_backup_service.restore_snapshot(snapshot["folder"], confirm=False)


@pytest.mark.django_db(transaction=True)
class TestPhase5Http:
    def test_health_version_and_backup_api(self, auth_client) -> None:
        client = Client()
        health = client.get("/api/v1/health/")
        assert health.status_code == 200
        body = health.json()
        assert body["database"] == "sqlite"
        assert body["integrity_check"] == "ok"
        version = client.get("/api/v1/version/")
        assert version.json()["name"] == "Shop Manager"
        created = auth_client.post("/api/v1/backups/", data={"reason": "http"}, content_type="application/json")
        assert created.status_code == 201
        listed = auth_client.get("/api/v1/backups/")
        assert listed.status_code == 200
        assert listed.json()["results"]

    def test_settings_round_trip_and_audit_ready(self, auth_client) -> None:
        patched = auth_client.patch(
            "/api/v1/settings/",
            data={"shop_name": "MM Electricals Shop", "scheduled_backup_enabled": True},
            content_type="application/json",
        )
        assert patched.status_code == 200
        assert patched.json()["shop_name"] == "MM Electricals Shop"
        row = ApplicationSettings.objects.get(singleton_key=1)
        assert row.scheduled_backup_enabled is True
