"""Transcode oversized call recordings to 8kHz mono in place.

FreeSWITCH was recording at 48kHz/16-bit/stereo (192 KB/s), producing files
~12x larger than telephone audio needs. This downsamples existing WAVs to
8000Hz/1ch, shrinking them ~12x with no meaningful quality loss (the source
calls are 8kHz narrowband anyway). Filenames/paths are unchanged, so the DB
needs no update.

Safety:
  - Transcodes to a temp file, verifies it's a valid smaller WAV, then does an
    atomic os.replace() — a crash mid-run never corrupts an original.
  - Idempotent: skips files already <=8kHz mono, so it's safe to re-run.
  - Preserves owner/group/mode of the original.

Usage:
  manage.py downsample_recordings --min-mb 5 --dry-run
  manage.py downsample_recordings --min-mb 5
"""
import contextlib
import os
import subprocess
import tempfile
import wave

from django.conf import settings
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Downsample oversized recordings to 8kHz mono in place.'

    def add_arguments(self, parser):
        parser.add_argument('--min-mb', type=float, default=5.0,
                            help='Only process files larger than this (MB).')
        parser.add_argument('--rate', type=int, default=8000)
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **opts):
        rec_dir = getattr(settings, 'FREESWITCH_RECORDINGS_DIR',
                          '/var/lib/freeswitch/recordings')
        min_bytes = opts['min_mb'] * 1_000_000
        rate = opts['rate']
        dry = opts['dry_run']

        wavs = []
        for root, _dirs, files in os.walk(rec_dir):
            for name in files:
                if name.lower().endswith('.wav'):
                    wavs.append(os.path.join(root, name))

        total_before = total_after = 0
        done = skipped = failed = 0

        for path in wavs:
            try:
                size = os.path.getsize(path)
            except OSError:
                continue
            if size < min_bytes:
                continue

            # Skip if already at/below target (idempotent re-runs)
            try:
                with contextlib.closing(wave.open(path, 'rb')) as w:
                    if w.getnchannels() <= 1 and w.getframerate() <= rate:
                        skipped += 1
                        continue
            except Exception:
                # Not a readable WAV header — leave it untouched.
                skipped += 1
                continue

            total_before += size
            if dry:
                est = int(size * (rate / 48000.0) / 2)  # /2 for stereo->mono
                total_after += est
                self.stdout.write(
                    f'WOULD shrink {os.path.basename(path)}  '
                    f'{size/1e6:.1f}MB -> ~{est/1e6:.1f}MB')
                done += 1
                continue

            try:
                st = os.stat(path)
                fd, tmp = tempfile.mkstemp(suffix='.wav', dir=os.path.dirname(path))
                os.close(fd)
                # sox: resample to `rate`, mix down to 1 channel
                subprocess.run(
                    ['sox', path, '-r', str(rate), '-c', '1', tmp],
                    check=True, capture_output=True)
                new_size = os.path.getsize(tmp)
                # Verify: valid WAV, and actually smaller
                with contextlib.closing(wave.open(tmp, 'rb')) as w:
                    assert w.getframerate() == rate and w.getnchannels() == 1
                if new_size == 0 or new_size >= size:
                    os.unlink(tmp)
                    failed += 1
                    self.stderr.write(f'SKIP (not smaller): {path}')
                    continue
                # Preserve ownership + mode, then atomic swap
                os.chown(tmp, st.st_uid, st.st_gid)
                os.chmod(tmp, st.st_mode)
                os.replace(tmp, path)
                total_after += new_size
                done += 1
                self.stdout.write(
                    f'shrunk {os.path.basename(path)}  '
                    f'{size/1e6:.1f}MB -> {new_size/1e6:.1f}MB')
            except Exception as e:
                failed += 1
                if os.path.exists(tmp):
                    with contextlib.suppress(OSError):
                        os.unlink(tmp)
                self.stderr.write(f'FAILED {path}: {e}')

        self.stdout.write(self.style.SUCCESS(
            f'\n{"DRY-RUN " if dry else ""}processed={done} skipped={skipped} '
            f'failed={failed}  '
            f'{total_before/1e9:.2f}GB -> {total_after/1e9:.2f}GB'))
