"""Restore a named snapshot after creating a safety copy of the live database."""

from django.core.management.base import BaseCommand, CommandError

from apps.core.backup import snapshot_backup_service


class Command(BaseCommand):
    help = "Restore backups/<folder> after an explicit --confirm flag."

    def add_arguments(self, parser):
        parser.add_argument("folder")
        parser.add_argument("--confirm", action="store_true")

    def handle(self, *args, **options):
        if not options["confirm"]:
            raise CommandError("Refusing to restore without --confirm.")
        result = snapshot_backup_service.restore_snapshot(options["folder"], confirm=True)
        self.stdout.write(self.style.SUCCESS(f"Restored {result['restored']}. Safety copy: {result['safety_folder']}"))
