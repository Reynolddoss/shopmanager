"""
Shop logo used on printed bills.

The file lives under MEDIA_ROOT/branding. Printing embeds it as a data URI so
the logo is already on the page when the browser opens the print dialog.
"""

from __future__ import annotations

import base64
from pathlib import Path

from django.core.files.uploadedfile import UploadedFile
from rest_framework.exceptions import ValidationError

from apps.core.models import ApplicationSettings


class ShopLogoService:
    """Validate, store, and encode the single bill logo."""

    MAX_BYTES = 2 * 1024 * 1024
    ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
    MIME_BY_EXTENSION = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
        ".gif": "image/gif",
    }

    def assign(self, settings_row: ApplicationSettings, upload: UploadedFile) -> ApplicationSettings:
        """Replace the current logo after checking type and size."""
        self._validate(upload)
        if settings_row.logo:
            settings_row.logo.delete(save=False)
        settings_row.logo = upload
        settings_row.save(update_fields=["logo", "updated_at"])
        return settings_row

    def clear(self, settings_row: ApplicationSettings) -> ApplicationSettings:
        """Remove the uploaded logo. Bills then use the built-in mark."""
        if settings_row.logo:
            settings_row.logo.delete(save=False)
            settings_row.logo = None
            settings_row.save(update_fields=["logo", "updated_at"])
        return settings_row

    def data_uri(self, settings_row: ApplicationSettings | None) -> str:
        """Return a data URI for the print HTML, or an empty string when no logo is stored."""
        if settings_row is None or not settings_row.logo:
            return ""
        try:
            path = Path(settings_row.logo.path)
            raw = path.read_bytes()
        except (OSError, ValueError):
            return ""
        mime = self.MIME_BY_EXTENSION.get(path.suffix.lower(), "image/png")
        encoded = base64.b64encode(raw).decode("ascii")
        return f"data:{mime};base64,{encoded}"

    def _validate(self, upload: UploadedFile) -> None:
        """Reject anything that is not a small picture."""
        ext = Path(upload.name or "logo.png").suffix.lower()
        if ext not in self.ALLOWED_EXTENSIONS:
            raise ValidationError({"image": "Use a JPG, PNG, WEBP, or GIF logo."})
        size = getattr(upload, "size", None) or 0
        if size > self.MAX_BYTES:
            raise ValidationError({"image": "Logo must be 2 MB or smaller."})


shop_logo_service = ShopLogoService()
