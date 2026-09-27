"""
Backup, migrate, then integrity-check. Run by the packaged launcher on every start.

Most starts have nothing to migrate and return immediately, so routine launches
do not fill the backup folder and push real backups out of retention.
"""

from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.core.backup import snapshot_backup_service, sqlite_integrity_service
from apps.core.health import health_service


class Command(BaseCommand):
    help = "Take a pre-upgrade backup, apply migrations, then verify SQLite."

    def handle(self, *args, **options):
        if health_service.is_fresh_database():
            health_service.apply_pending_migrations()
            self.stdout.write(self.style.SUCCESS("New shop database created."))
            return
        pending = health_service.pending_migrations()
        if not pending:
            self.stdout.write("Database schema is current; no upgrade needed.")
            return
        self.stdout.write(f"Applying {len(pending)} migration(s): {', '.join(pending)}")
        backup = snapshot_backup_service.create_snapshot(reason="pre_upgrade")
        self.stdout.write(f"Safety backup: {backup['folder']}")
        try:
            health_service.apply_pending_migrations()
        except Exception as exc:
            snapshot_backup_service.restore_snapshot(backup["folder"], confirm=True)
            raise CommandError(f"Upgrade failed; live database restored from {backup['folder']}: {exc}") from exc
        live = Path(str(settings.DATABASES["default"]["NAME"]))
        ok, message = sqlite_integrity_service.integrity_ok(live)
        if not ok:
            snapshot_backup_service.restore_snapshot(backup["folder"], confirm=True)
            raise CommandError(f"Integrity failed after migrate ({message}); restored {backup['folder']}")
        self.stdout.write(self.style.SUCCESS("Upgrade finished. Database integrity is ok."))
