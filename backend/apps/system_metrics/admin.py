from django.contrib import admin

from .models import CpuPeak, SystemMetricSample, PostgresPerf


@admin.register(CpuPeak)
class CpuPeakAdmin(admin.ModelAdmin):
    list_display = ('window_start', 'system_cpu_peak', 'freeswitch_cpu_peak',
                    'freeswitch_cpu_peak_norm', 'load_avg_1m', 'freeswitch_running',
                    'samples')
    list_filter = ('freeswitch_running',)
    date_hierarchy = 'window_start'
    ordering = ('-window_start',)


@admin.register(SystemMetricSample)
class SystemMetricSampleAdmin(admin.ModelAdmin):
    list_display = ('window_start', 'mem_used_percent_peak', 'swap_used_percent_peak',
                    'mem_pressure_some_peak', 'disk_busy_percent_peak',
                    'disk_read_latency_ms', 'disk_write_latency_ms',
                    'net_recv_bytes_per_sec', 'net_sent_bytes_per_sec', 'samples')
    date_hierarchy = 'window_start'
    ordering = ('-window_start',)


@admin.register(PostgresPerf)
class PostgresPerfAdmin(admin.ModelAdmin):
    list_display = ('window_start', 'active_connections_peak', 'total_connections_peak',
                    'max_connections', 'cache_hit_ratio', 'commits_per_sec',
                    'rollbacks_per_sec', 'deadlocks', 'longest_query_seconds', 'samples')
    date_hierarchy = 'window_start'
    ordering = ('-window_start',)
