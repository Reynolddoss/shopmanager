"""Run a backup when scheduled backups are enabled and due."""

from django.core.management.base import BaseCommand

from apps.core.backup import snapshot_backup_service


class Command(BaseCommand):
    help = "Create a backup if the shop schedule says one is due."

    def handle(self, *args, **options):
        result = snapshot_backup_service.maybe_run_schedule()
        if result is None:
            self.stdout.write("No scheduled backup due.")
            return
        self.stdout.write(self.style.SUCCESS(f"Scheduled backup written: {result['folder']}"))
