import uuid
from django.db import models


class CpuPeak(models.Model):
    """
    Peak CPU usage over a rollup window (default 5 minutes).

    A sampler reads CPU roughly once per minute and, at the end of each window,
    writes ONE row holding the highest values seen during that window — for both
    the whole server and the FreeSWITCH process. This keeps spikes visible
    (~288 rows/day) without storing every per-minute sample.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Window boundaries (UTC, timezone-aware). window_start is indexed for range
    # queries / daily-max rollups.
    window_start = models.DateTimeField(db_index=True)
    window_end = models.DateTimeField()

    # Peak percentages within the window. System = whole box (0-100, already
    # normalized across cores). FreeSWITCH process % can exceed 100 on multi-core
    # boxes (psutil reports sum across cores), so it is stored un-normalized and
    # a normalized copy is kept alongside for easy comparison to system %.
    system_cpu_peak = models.FloatField(help_text='Peak whole-server CPU %, 0-100')
    freeswitch_cpu_peak = models.FloatField(
        help_text='Peak freeswitch process CPU % (may exceed 100 = sum over cores)')
    freeswitch_cpu_peak_norm = models.FloatField(
        help_text='freeswitch_cpu_peak divided by core count, comparable to system %')

    # Context captured at the moment of the system-CPU peak, useful for triage.
    cpu_count = models.IntegerField(help_text='Logical CPU cores at sample time')
    load_avg_1m = models.FloatField(null=True, blank=True)
    freeswitch_running = models.BooleanField(default=True)
    samples = models.IntegerField(default=0, help_text='Number of samples in this window')

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'system_cpu_peak'
        ordering = ('-window_start',)
        verbose_name = 'CPU peak'
        verbose_name_plural = 'CPU peaks'

    def __str__(self):
        return (f'{self.window_start:%Y-%m-%d %H:%M} '
                f'sys={self.system_cpu_peak:.0f}% fs={self.freeswitch_cpu_peak:.0f}%')


class SystemMetricSample(models.Model):
    """
    Peak/rate system health metrics over a rollup window, mirroring CpuPeak.

    One row per window (~5 min) holding RAM pressure, disk I/O latency, and
    network throughput. Rates (throughput, I/O) are computed from counter
    deltas across the window; pressure/latency store the peak seen.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    window_start = models.DateTimeField(db_index=True)
    window_end = models.DateTimeField()

    # --- RAM pressure ---
    # Linux PSI: share of time (0-100%) some/all tasks stalled on memory over
    # the window (peak of the 10s avg). null if /proc/pressure unavailable.
    mem_pressure_some_peak = models.FloatField(
        null=True, blank=True, help_text='Peak PSI memory "some" avg10 %, 0-100')
    mem_pressure_full_peak = models.FloatField(
        null=True, blank=True, help_text='Peak PSI memory "full" avg10 %, 0-100')
    mem_used_percent_peak = models.FloatField(help_text='Peak RAM used %, 0-100')
    swap_used_percent_peak = models.FloatField(help_text='Peak swap used %, 0-100')

    # --- Disk I/O latency ---
    # Average time per I/O op over the window, derived from busy-time and op-count
    # deltas (psutil disk_io_counters). Aggregated across all physical disks.
    disk_read_latency_ms = models.FloatField(
        help_text='Avg read latency over window (ms/op)')
    disk_write_latency_ms = models.FloatField(
        help_text='Avg write latency over window (ms/op)')
    disk_busy_percent_peak = models.FloatField(
        help_text='Peak disk busy % (util) over the window')

    # --- Network throughput ---
    # Bytes/sec averaged over the window from net_io_counters deltas, summed
    # over all non-loopback interfaces.
    net_recv_bytes_per_sec = models.FloatField(help_text='Avg inbound throughput B/s')
    net_sent_bytes_per_sec = models.FloatField(help_text='Avg outbound throughput B/s')

    samples = models.IntegerField(default=0, help_text='Number of samples in this window')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'system_metric_sample'
        ordering = ('-window_start',)
        verbose_name = 'system metric sample'
        verbose_name_plural = 'system metric samples'

    def __str__(self):
        return (f'{self.window_start:%Y-%m-%d %H:%M} '
                f'mem={self.mem_used_percent_peak:.0f}% '
                f'net_rx={self.net_recv_bytes_per_sec/1e6:.1f}MB/s')


class PostgresPerf(models.Model):
    """
    PostgreSQL performance snapshot per rollup window.

    Sampled from pg_stat_* on the 'default' (primary) database. Rates (commits,
    fetches, etc.) are per-second averages over the window from counter deltas;
    gauges (connections, cache hit ratio) store the peak/last value.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    window_start = models.DateTimeField(db_index=True)
    window_end = models.DateTimeField()

    # Connection pressure.
    active_connections_peak = models.IntegerField(
        help_text='Peak backends in state=active')
    total_connections_peak = models.IntegerField(
        help_text='Peak total backends')
    max_connections = models.IntegerField(
        help_text='Configured max_connections')

    # Cache efficiency (peak of ratio over window, 0-100).
    cache_hit_ratio = models.FloatField(
        help_text='blks_hit / (blks_hit + blks_read) %, 0-100')

    # Throughput (per-second averages from pg_stat_database deltas).
    commits_per_sec = models.FloatField(help_text='xact_commit /s')
    rollbacks_per_sec = models.FloatField(help_text='xact_rollback /s')
    tuples_returned_per_sec = models.FloatField(help_text='tup_returned /s')
    tuples_fetched_per_sec = models.FloatField(help_text='tup_fetched /s')

    # Contention.
    deadlocks = models.IntegerField(default=0, help_text='Deadlocks during window')
    longest_query_seconds = models.FloatField(
        null=True, blank=True, help_text='Longest running query seen (s)')

    samples = models.IntegerField(default=0, help_text='Number of samples in this window')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'postgres_perf'
        ordering = ('-window_start',)
        verbose_name = 'PostgreSQL performance sample'
        verbose_name_plural = 'PostgreSQL performance samples'

    def __str__(self):
        return (f'{self.window_start:%Y-%m-%d %H:%M} '
                f'conns={self.active_connections_peak}/{self.total_connections_peak} '
                f'hit={self.cache_hit_ratio:.1f}%')
