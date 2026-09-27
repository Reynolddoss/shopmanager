"""Create a validated SQLite + CSV snapshot. Safe to run from Task Scheduler."""

from django.core.management.base import BaseCommand

from apps.core.backup import snapshot_backup_service


class Command(BaseCommand):
    help = "Write a timestamped shop backup (SQLite + CSV + metadata)."

    def handle(self, *args, **options):
        result = snapshot_backup_service.create_snapshot(reason="management_command")
        self.stdout.write(self.style.SUCCESS(f"Backup written: {result['folder']}"))
