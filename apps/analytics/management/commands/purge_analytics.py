from django.core.management.base import BaseCommand

from apps.analytics.tracking import purge


class Command(BaseCommand):
    help = "Supprime les mesures d'audience plus anciennes que ANALYTICS_RETENTION_DAYS (faite aussi chaque jour)."

    def handle(self, *args, **options):
        self.stdout.write(f"{purge()} lignes supprimées.")
