from django.contrib import admin
from .models import WorkingHours, WorkingHoursDay, WorkingHoursHoliday


class WorkingHoursDayInline(admin.TabularInline):
    model = WorkingHoursDay
    extra = 0
    fields = ['day_of_week', 'is_open', 'open_time', 'close_time']
    ordering = ['day_of_week']


class WorkingHoursHolidayInline(admin.TabularInline):
    model = WorkingHoursHoliday
    extra = 0
    fields = ['holiday_date', 'holiday_name']
    ordering = ['holiday_date']


@admin.register(WorkingHours)
class WorkingHoursAdmin(admin.ModelAdmin):
    list_display = [
        'working_hours_name', 'dialplan_extension', 'timezone',
        'working_hours_enabled', 'open_dest_type', 'closed_dest_type',
        'tenant', 'domain',
    ]
    list_filter = ['working_hours_enabled', 'tenant', 'domain']
    search_fields = ['working_hours_name', 'dialplan_extension']
    readonly_fields = ['working_hours_uuid', 'insert_date', 'update_date']
    inlines = [WorkingHoursDayInline, WorkingHoursHolidayInline]
    fieldsets = [
        ('Identity', {
            'fields': ['working_hours_uuid', 'working_hours_name', 'working_hours_description',
                       'working_hours_enabled', 'dialplan_extension', 'timezone', 'tenant', 'domain'],
        }),
        ('Open Hours Destination', {
            'fields': ['open_dest_type', 'open_dest_target_uuid', 'open_dest_external_number'],
        }),
        ('Closed Hours Destination', {
            'fields': ['closed_dest_type', 'closed_dest_target_uuid', 'closed_dest_external_number'],
        }),
        ('Audit', {
            'fields': ['insert_date', 'insert_user', 'update_date', 'update_user'],
            'classes': ['collapse'],
        }),
    ]
