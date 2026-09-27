"""
Product image attach / replace / clear.

Files live under MEDIA_ROOT (shop data dir). Catalog create stays JSON;
photos are uploaded via the dedicated multipart endpoint after the product exists.
"""

from __future__ import annotations

from pathlib import Path

from django.core.files.uploadedfile import UploadedFile
from rest_framework.exceptions import ValidationError

from apps.products.models import Product


class ProductImageService:
    """Validate and store a single catalog photo per product."""

    MAX_BYTES = 5 * 1024 * 1024
    ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}

    def assign(self, product: Product, upload: UploadedFile) -> Product:
        self._validate(upload)
        if product.image:
            product.image.delete(save=False)
        product.image = upload
        product.save(update_fields=["image", "updated_at"])
        return product

    def clear(self, product: Product) -> Product:
        if product.image:
            product.image.delete(save=False)
            product.image = None
            product.save(update_fields=["image", "updated_at"])
        return product

    def _validate(self, upload: UploadedFile) -> None:
        name = upload.name or "photo.jpg"
        ext = Path(name).suffix.lower()
        if ext not in self.ALLOWED_EXTENSIONS:
            raise ValidationError(
                {"image": "Use a JPG, PNG, WEBP, or GIF picture."},
            )
        size = getattr(upload, "size", None) or 0
        if size > self.MAX_BYTES:
            raise ValidationError({"image": "Picture must be 5 MB or smaller."})


product_image_service = ProductImageService()
