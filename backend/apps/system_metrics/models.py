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
