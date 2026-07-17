from django.contrib import admin

from .models import CpuPeak


@admin.register(CpuPeak)
class CpuPeakAdmin(admin.ModelAdmin):
    list_display = ('window_start', 'system_cpu_peak', 'freeswitch_cpu_peak',
                    'freeswitch_cpu_peak_norm', 'load_avg_1m', 'freeswitch_running',
                    'samples')
    list_filter = ('freeswitch_running',)
    date_hierarchy = 'window_start'
    ordering = ('-window_start',)
