from django.core.management.base import BaseCommand
from core import cache_version


class Command(BaseCommand):
    help = 'Invalidate all pbx: and client: API response caches system-wide.'

    def handle(self, *args, **options):
        new_version = cache_version.bump()
        self.stdout.write(self.style.SUCCESS(f'Cache flushed — now at version {new_version}'))
