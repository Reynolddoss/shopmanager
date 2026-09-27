"""
Windows-safe locations for business data, backups, and logs.

Installers must not store the live SQLite file next to the .exe. Upgrades
replace program files; they must not replace the shop database.
"""

from __future__ import annotations

import os
from pathlib import Path

from django.conf import settings


class DataDirectoryService:
    """Resolve the shop data root (same folder as the live SQLite file)."""

    def root(self) -> Path:
        """
        Return the shop data root.

        The installed app sets MM_DATA_DIR to %LOCALAPPDATA%\\MMElectricals;
        development and tests use backend/data. Backups must live beside the
        database they protect, so this always follows settings.SHOP_DATA_ROOT.
        """
        if os.environ.get("PYTEST_VERSION"):
            path = Path(settings.BASE_DIR) / "data"
        else:
            path = Path(settings.SHOP_DATA_ROOT)
        path.mkdir(parents=True, exist_ok=True)
        return path

    def database_file(self) -> Path:
        return self.root() / "mm_electricals.sqlite3"

    def backup_root(self) -> Path:
        path = self.root() / "backups"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def log_root(self) -> Path:
        path = self.root() / "logs"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def media_root(self) -> Path:
        """Product pictures and other uploads — kept with the shop DB, not the installer."""
        path = self.root() / "media"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def safe_child(self, folder_name: str) -> Path:
        """Reject path traversal when restoring a named backup folder."""
        if not folder_name or ".." in folder_name or "/" in folder_name or "\\" in folder_name:
            raise ValueError("Invalid backup folder name.")
        target = (self.backup_root() / folder_name).resolve()
        root = self.backup_root().resolve()
        if root not in target.parents and target != root:
            raise ValueError("Backup path is outside the backup directory.")
        return target


data_directory_service = DataDirectoryService()
