"""
Sample system + PostgreSQL health over a window and store one rollup row each.

Runs as a short-lived process (systemd timer, one invocation per window),
mirroring sample_cpu_peak. Within the window it samples once per interval,
tracks peaks and computes rates from counter deltas, then writes ONE
SystemMetricSample row and ONE PostgresPerf row and exits.

Metrics captured:
  * RAM pressure       - Linux PSI (/proc/pressure/memory) + RAM/swap used %
  * Disk I/O latency   - avg ms/op from disk_io_counters deltas, + busy %
  * Network throughput - B/s from net_io_counters deltas
  * PostgreSQL perf    - pg_stat_database rates, connections, cache hit, deadlocks

Typical: --window 270 --interval 60  → ~4 samples, one row per 5 min.
"""
import time

from django.core.management.base import BaseCommand
from django.db import connections
from django.utils import timezone

import psutil

from apps.system_metrics.models import SystemMetricSample, PostgresPerf


def _read_mem_pressure():
    """Return (some_avg10, full_avg10) from /proc/pressure/memory, or (None, None)."""
    some = full = None
    try:
        with open('/proc/pressure/memory') as fh:
            for line in fh:
                parts = dict(
                    kv.split('=') for kv in line.split()[1:] if '=' in kv)
                avg10 = float(parts.get('avg10', 'nan'))
                if line.startswith('some'):
                    some = avg10
                elif line.startswith('full'):
                    full = avg10
    except (OSError, ValueError):
        pass
    return some, full


def _pg_stats():
    """Snapshot pg_stat_* counters/gauges from the default DB. Returns dict or None."""
    try:
        conn = connections['default']
        with conn.cursor() as cur:
            db_name = conn.settings_dict['NAME']
            cur.execute(
                """
                SELECT xact_commit, xact_rollback, tup_returned, tup_fetched,
                       blks_hit, blks_read, deadlocks
                FROM pg_stat_database WHERE datname = %s
                """, [db_name])
            row = cur.fetchone()
            if row is None:
                return None
            commit, rollback, tup_ret, tup_fetch, blks_hit, blks_read, deadlocks = row

            cur.execute("SELECT count(*), count(*) FILTER (WHERE state='active') "
                        "FROM pg_stat_activity WHERE datname = %s", [db_name])
            total_conn, active_conn = cur.fetchone()

            cur.execute("SELECT setting::int FROM pg_settings WHERE name='max_connections'")
            max_conn = cur.fetchone()[0]

            cur.execute(
                """
                SELECT COALESCE(max(EXTRACT(EPOCH FROM (now() - query_start))), 0)
                FROM pg_stat_activity
                WHERE datname = %s AND state = 'active' AND query_start IS NOT NULL
                """, [db_name])
            longest = float(cur.fetchone()[0])

            hit_ratio = 100.0 * blks_hit / (blks_hit + blks_read) if (blks_hit + blks_read) else 100.0
            return {
                'commit': commit, 'rollback': rollback,
                'tup_ret': tup_ret, 'tup_fetch': tup_fetch,
                'deadlocks': deadlocks,
                'total_conn': total_conn, 'active_conn': active_conn,
                'max_conn': max_conn, 'longest': longest, 'hit_ratio': hit_ratio,
            }
    except Exception:
        return None


class Command(BaseCommand):
    help = 'Sample system + PostgreSQL metrics over a window and store the rollup.'

    def add_arguments(self, parser):
        parser.add_argument('--window', type=int, default=270,
                            help='Window length in seconds (default 270).')
        parser.add_argument('--interval', type=int, default=60,
                            help='Seconds between samples (default 60).')

    def handle(self, *args, **opts):
        window = max(opts['window'], opts['interval'])
        interval = opts['interval']
        n_samples = max(1, window // interval)

        window_start = timezone.now()

        # Baseline counters for delta-based rates.
        disk0 = psutil.disk_io_counters()
        net0 = psutil.net_io_counters()
        pg0 = _pg_stats()
        t0 = time.monotonic()

        # Peaks / gauges tracked across samples.
        mem_some_peak = mem_full_peak = None
        mem_used_peak = swap_used_peak = 0.0
        disk_busy_peak = 0.0
        pg_active_peak = pg_total_peak = 0
        pg_hit_peak = 0.0
        pg_longest_peak = 0.0
        pg_max_conn = 0

        taken = 0
        for _ in range(n_samples):
            time.sleep(interval)
            taken += 1

            some, full = _read_mem_pressure()
            if some is not None:
                mem_some_peak = some if mem_some_peak is None else max(mem_some_peak, some)
            if full is not None:
                mem_full_peak = full if mem_full_peak is None else max(mem_full_peak, full)

            mem_used_peak = max(mem_used_peak, psutil.virtual_memory().percent)
            swap_used_peak = max(swap_used_peak, psutil.swap_memory().percent)

            pg = _pg_stats()
            if pg is not None:
                pg_active_peak = max(pg_active_peak, pg['active_conn'])
                pg_total_peak = max(pg_total_peak, pg['total_conn'])
                pg_hit_peak = max(pg_hit_peak, pg['hit_ratio'])
                pg_longest_peak = max(pg_longest_peak, pg['longest'])
                pg_max_conn = pg['max_conn']

        window_end = timezone.now()
        elapsed = max(time.monotonic() - t0, 1e-6)

        # --- Disk I/O latency + busy % from deltas ---
        disk1 = psutil.disk_io_counters()
        read_lat = write_lat = 0.0
        if disk0 and disk1:
            d_reads = disk1.read_count - disk0.read_count
            d_writes = disk1.write_count - disk0.write_count
            # read_time/write_time are cumulative ms spent in I/O.
            if d_reads > 0:
                read_lat = (disk1.read_time - disk0.read_time) / d_reads
            if d_writes > 0:
                write_lat = (disk1.write_time - disk0.write_time) / d_writes
            busy_ms = getattr(disk1, 'busy_time', 0) - getattr(disk0, 'busy_time', 0)
            disk_busy_peak = min(100.0, 100.0 * busy_ms / (elapsed * 1000.0))

        # --- Network throughput from deltas ---
        net1 = psutil.net_io_counters()
        net_recv = net_sent = 0.0
        if net0 and net1:
            net_recv = max(0.0, (net1.bytes_recv - net0.bytes_recv) / elapsed)
            net_sent = max(0.0, (net1.bytes_sent - net0.bytes_sent) / elapsed)

        sys_row = SystemMetricSample.objects.create(
            window_start=window_start, window_end=window_end,
            mem_pressure_some_peak=(round(mem_some_peak, 2) if mem_some_peak is not None else None),
            mem_pressure_full_peak=(round(mem_full_peak, 2) if mem_full_peak is not None else None),
            mem_used_percent_peak=round(mem_used_peak, 1),
            swap_used_percent_peak=round(swap_used_peak, 1),
            disk_read_latency_ms=round(read_lat, 2),
            disk_write_latency_ms=round(write_lat, 2),
            disk_busy_percent_peak=round(disk_busy_peak, 1),
            net_recv_bytes_per_sec=round(net_recv, 1),
            net_sent_bytes_per_sec=round(net_sent, 1),
            samples=taken,
        )

        # --- PostgreSQL perf from deltas ---
        pg1 = _pg_stats()
        if pg0 and pg1:
            def rate(key):
                return max(0.0, (pg1[key] - pg0[key]) / elapsed)
            PostgresPerf.objects.create(
                window_start=window_start, window_end=window_end,
                active_connections_peak=pg_active_peak,
                total_connections_peak=pg_total_peak,
                max_connections=pg_max_conn or pg1['max_conn'],
                cache_hit_ratio=round(pg_hit_peak, 2),
                commits_per_sec=round(rate('commit'), 2),
                rollbacks_per_sec=round(rate('rollback'), 2),
                tuples_returned_per_sec=round(rate('tup_ret'), 2),
                tuples_fetched_per_sec=round(rate('tup_fetch'), 2),
                deadlocks=max(0, pg1['deadlocks'] - pg0['deadlocks']),
                longest_query_seconds=round(pg_longest_peak, 2),
                samples=taken,
            )
            pg_msg = f'pg_conns={pg_active_peak}/{pg_total_peak}'
        else:
            pg_msg = 'pg=unavailable'

        self.stdout.write(self.style.SUCCESS(
            f'Stored system metrics {sys_row.window_start:%H:%M}: '
            f'mem={sys_row.mem_used_percent_peak}% '
            f'net_rx={net_recv/1e6:.2f}MB/s {pg_msg} ({taken} samples)'))
