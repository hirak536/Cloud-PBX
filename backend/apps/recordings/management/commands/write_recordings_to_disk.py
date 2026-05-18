"""
Management command: write_recordings_to_disk

Writes all Recording objects that have base64 audio data to disk at
FREESWITCH_SOUNDS_DIR/<recording_filename> so FreeSWITCH can play them.

Run once after migrating/importing recordings, or whenever IVR audio is
silent despite recordings being playable in the UI.

Usage:
    python manage.py write_recordings_to_disk
    python manage.py write_recordings_to_disk --dry-run
"""
import base64
import os

from django.conf import settings
from django.core.management.base import BaseCommand

from apps.recordings.models import Recording


class Command(BaseCommand):
    help = 'Write all recordings with base64 data to disk for FreeSWITCH.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be written without writing anything.',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        sounds_dir = getattr(settings, 'FREESWITCH_SOUNDS_DIR', '')
        if not sounds_dir:
            self.stderr.write(self.style.ERROR('FREESWITCH_SOUNDS_DIR is not set.'))
            return

        qs = Recording.objects.exclude(recording_base64='').exclude(recording_filename='')
        total = qs.count()
        self.stdout.write(f'Found {total} recording(s) with base64 data.')

        written = skipped = errors = 0
        for rec in qs.iterator():
            dest = os.path.join(sounds_dir, rec.recording_filename)
            if os.path.isfile(dest):
                self.stdout.write(f'  SKIP (exists)  {dest}')
                skipped += 1
                continue

            if dry_run:
                self.stdout.write(f'  WOULD WRITE    {dest}')
                written += 1
                continue

            try:
                audio_data = base64.b64decode(rec.recording_base64)
                os.makedirs(os.path.dirname(dest) or sounds_dir, exist_ok=True)
                with open(dest, 'wb') as f:
                    f.write(audio_data)
                self.stdout.write(self.style.SUCCESS(f'  WROTE          {dest}'))
                written += 1
            except Exception as exc:
                self.stderr.write(self.style.ERROR(f'  ERROR          {dest}: {exc}'))
                errors += 1

        self.stdout.write('')
        if dry_run:
            self.stdout.write(f'Dry run complete. Would write {written}, skip {skipped}.')
        else:
            self.stdout.write(
                self.style.SUCCESS(f'Done. Written: {written}, skipped: {skipped}, errors: {errors}.')
            )
