"""Management command to backfill message_len for voicemail messages stored as 0."""
import os
import wave

from django.core.management.base import BaseCommand

from apps.voicemails.models import VoicemailMessage


class Command(BaseCommand):
    help = 'Backfill message_len (duration in seconds) for voicemails where it is 0.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Report what would be updated without writing to the database.',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']

        qs = VoicemailMessage.objects.using('voicemail_sqlite').filter(message_len=0)
        total = qs.count()
        self.stdout.write(f'Found {total} voicemail(s) with message_len=0.')

        fixed = 0
        missing = 0

        for msg in qs.iterator():
            if not msg.file_path or not os.path.isfile(msg.file_path):
                missing += 1
                self.stdout.write(
                    self.style.WARNING(f'  SKIP {msg.uuid}: file not found ({msg.file_path})')
                )
                continue

            file_size = os.path.getsize(msg.file_path)
            try:
                with wave.open(msg.file_path, 'r') as wf:
                    nframes = wf.getnframes()
                    framerate = wf.getframerate()
                    duration = max(1, round(nframes / framerate)) if nframes > 0 else 0
                self.stdout.write(
                    f'  INFO {msg.uuid}: size={file_size}B frames={nframes} rate={framerate} => {duration}s  path={msg.file_path}'
                )
            except Exception as exc:
                self.stdout.write(
                    self.style.WARNING(f'  SKIP {msg.uuid}: could not read WAV ({exc})  size={file_size}B  path={msg.file_path}')
                )
                continue

            if duration <= 0:
                continue

            self.stdout.write(f'  {"WOULD UPDATE" if dry_run else "UPDATE"} {msg.uuid}: {duration}s')

            if not dry_run:
                VoicemailMessage.objects.using('voicemail_sqlite').filter(
                    uuid=msg.uuid
                ).update(message_len=duration)
                fixed += 1
            else:
                fixed += 1

        self.stdout.write(
            self.style.SUCCESS(
                f'\nDone. {"Would fix" if dry_run else "Fixed"} {fixed}/{total} record(s). '
                f'{missing} skipped (file missing).'
            )
        )
