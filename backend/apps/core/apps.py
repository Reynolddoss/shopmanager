from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.core"

    def ready(self) -> None:
        """Register SQLite pragma handlers when the app loads."""
        from apps.core import sqlite  # noqa: F401
