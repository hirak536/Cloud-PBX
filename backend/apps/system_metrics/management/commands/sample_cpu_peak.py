"""
Sample CPU usage over a window and store the peak.

Runs as a short-lived process (driven by a systemd timer, one invocation per
window). Within the window it samples once per interval, tracks the maximum
whole-server CPU % and the maximum freeswitch-process CPU %, then writes ONE
CpuPeak row and exits.

Typical: --window 300 --interval 60  → 5 samples, one peak row per 5 min.
"""
import time
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

import psutil

from apps.system_metrics.models import CpuPeak


def _find_freeswitch_proc():
    for p in psutil.process_iter(['name']):
        try:
            if p.info['name'] == 'freeswitch':
                return p
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return None


class Command(BaseCommand):
    help = 'Sample CPU over a window and store the peak (system + freeswitch).'

    def add_arguments(self, parser):
        parser.add_argument('--window', type=int, default=300,
                            help='Window length in seconds (default 300 = 5 min).')
        parser.add_argument('--interval', type=int, default=60,
                            help='Seconds between samples (default 60).')

    def handle(self, *args, **opts):
        window = max(opts['window'], opts['interval'])
        interval = opts['interval']
        n_samples = max(1, window // interval)

        core_count = psutil.cpu_count(logical=True) or 1
        fs = _find_freeswitch_proc()

        window_start = timezone.now()

        sys_peak = 0.0
        fs_peak = 0.0
        load1_at_peak = None

        # Prime the per-process CPU counter (first call returns 0.0).
        if fs is not None:
            try:
                fs.cpu_percent(None)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                fs = None

        taken = 0
        for i in range(n_samples):
            # Blocking sample over `interval` seconds gives an accurate system %.
            sys_pct = psutil.cpu_percent(interval=interval)

            fs_pct = 0.0
            if fs is not None:
                try:
                    fs_pct = fs.cpu_percent(None)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    fs = _find_freeswitch_proc()  # process may have restarted

            taken += 1
            if sys_pct >= sys_peak:
                sys_peak = sys_pct
                try:
                    load1_at_peak = psutil.getloadavg()[0]
                except (OSError, AttributeError):
                    load1_at_peak = None
            if fs_pct > fs_peak:
                fs_peak = fs_pct

        window_end = timezone.now()

        row = CpuPeak.objects.create(
            window_start=window_start,
            window_end=window_end,
            system_cpu_peak=round(sys_peak, 1),
            freeswitch_cpu_peak=round(fs_peak, 1),
            freeswitch_cpu_peak_norm=round(fs_peak / core_count, 1),
            cpu_count=core_count,
            load_avg_1m=(round(load1_at_peak, 2) if load1_at_peak is not None else None),
            freeswitch_running=fs is not None,
            samples=taken,
        )
        self.stdout.write(self.style.SUCCESS(
            f'Stored CPU peak {row.window_start:%H:%M}: '
            f'sys={row.system_cpu_peak}% fs={row.freeswitch_cpu_peak}% '
            f'({taken} samples)'))
