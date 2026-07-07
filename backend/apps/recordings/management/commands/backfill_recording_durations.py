import os

from django.conf import settings
from django.core.management.base import BaseCommand

from apps.recordings.models import CallRecording
from apps.recordings.views import _wav_duration


class Command(BaseCommand):
    help = "Backfill call_recording_duration (and billsec) from the WAV file on disk for rows where it is 0."

    def add_arguments(self, parser):
        parser.add_argument('--all', action='store_true',
                            help='Recompute for every row, not just those with duration=0.')
        parser.add_argument('--dry-run', action='store_true',
                            help='Report what would change without saving.')

    def handle(self, *args, **opts):
        recordings_dir = getattr(settings, 'FREESWITCH_RECORDINGS_DIR', '/var/lib/freeswitch/recordings')
        qs = CallRecording.objects.all()
        if not opts['all']:
            qs = qs.filter(call_recording_duration=0)

        updated = missing = unchanged = 0
        for rec in qs.iterator():
            path = rec.call_recording_filename
            if not os.path.isabs(path):
                path = os.path.join(recordings_dir, path)
            if not os.path.isfile(path):
                missing += 1
                continue
            dur = _wav_duration(path)
            if dur <= 0:
                unchanged += 1
                continue
            if dur == rec.call_recording_duration:
                unchanged += 1
                continue
            if not opts['dry_run']:
                rec.call_recording_duration = dur
                # Only set billsec when it has no better value already.
                if not rec.call_recording_billsec:
                    rec.call_recording_billsec = dur
                rec.save(update_fields=['call_recording_duration', 'call_recording_billsec'])
            updated += 1

        prefix = '[dry-run] ' if opts['dry_run'] else ''
        self.stdout.write(self.style.SUCCESS(
            f"{prefix}updated={updated} unchanged={unchanged} file_missing={missing}"
        ))
