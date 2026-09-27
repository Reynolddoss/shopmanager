"""
SQLite safety for a business-critical desktop database.

Django does not enable WAL or foreign keys by default on every connection.
This module applies those pragmas once per connection so crashes and concurrent
reads (API + backup) do not corrupt the file.
"""

from __future__ import annotations

from django.db.backends.signals import connection_created
from django.dispatch import receiver


class SqlitePragmaConfigurator:
    """Apply durable, integrity-first SQLite pragmas on each new connection."""

    WAL_MODE = "WAL"
    SYNCHRONOUS = "NORMAL"
    BUSY_TIMEOUT_MS = 30000

    def apply(self, connection) -> None:
        """
        Enable WAL, foreign keys, and a busy timeout.

        WAL lets readers (health checks, backups) proceed while a writer holds
        a short transaction. Foreign keys protect master-data relationships.
        """
        if connection.vendor != "sqlite":
            return
        cursor = connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL;")
        cursor.execute("PRAGMA foreign_keys=ON;")
        cursor.execute(f"PRAGMA busy_timeout={self.BUSY_TIMEOUT_MS};")
        cursor.execute(f"PRAGMA synchronous={self.SYNCHRONOUS};")
        cursor.execute("PRAGMA temp_store=MEMORY;")


_configurator = SqlitePragmaConfigurator()


@receiver(connection_created)
def configure_sqlite_connection(sender, connection, **kwargs) -> None:
    """Signal handler so every new SQLite connection is configured the same way."""
    _configurator.apply(connection)
