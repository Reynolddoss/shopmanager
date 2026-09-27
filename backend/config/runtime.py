"""
Runtime environment for Django settings.

Decides where shop data lives, whether the API runs in packaged (production)
mode, the per-install secret key, and where the built React UI is. Kept free
of Django imports so settings.py can use it before Django is set up.
"""

from __future__ import annotations

import os
import secrets
import sys
from pathlib import Path


class RuntimeConfig:
    """Resolve environment-dependent settings for dev, tests, and the installed app."""

    SECRET_FILE_NAME = "secret_key.txt"
    DEV_SECRET_KEY = "django-insecure-mm-electricals-local-development-only"

    def __init__(self, base_dir: Path) -> None:
        self.base_dir = base_dir

    @property
    def packaged(self) -> bool:
        """True inside the installed desktop app (set by packaging/launch_api.py)."""
        return os.environ.get("MM_PACKAGED") == "1"

    @property
    def debug(self) -> bool:
        """DEBUG stays on for local development and off in the installed app unless forced."""
        raw = os.environ.get("MM_DEBUG")
        if raw is not None:
            return raw == "1"
        return not self.packaged

    def data_root(self) -> Path:
        """Single source of truth for SQLite, backups, logs, media, and the secret key."""
        override = os.environ.get("MM_DATA_DIR")
        path = Path(override).expanduser().resolve() if override else self.base_dir / "data"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def secret_key(self) -> str:
        """Random per-install key persisted next to the database; the dev key never ships."""
        from_env = os.environ.get("MM_SECRET_KEY")
        if from_env:
            return from_env
        if self.debug:
            return self.DEV_SECRET_KEY
        path = self.data_root() / self.SECRET_FILE_NAME
        if path.exists():
            existing = path.read_text(encoding="utf-8").strip()
            if existing:
                return existing
        generated = secrets.token_urlsafe(50)
        path.write_text(generated, encoding="utf-8")
        return generated

    def frontend_dist(self) -> Path:
        """Built React app: bundled inside the PyInstaller folder, or frontend/dist in the repo."""
        override = os.environ.get("MM_FRONTEND_DIST")
        if override:
            return Path(override).expanduser().resolve()
        bundle_dir = getattr(sys, "_MEIPASS", None)
        if getattr(sys, "frozen", False) and bundle_dir:
            return Path(bundle_dir) / "frontend_dist"
        return self.base_dir.parent / "frontend" / "dist"
