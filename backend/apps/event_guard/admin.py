from django.contrib import admin
from .models import EventGuard

@admin.register(EventGuard)
class EventGuardAdmin(admin.ModelAdmin):
    list_display = ['event_guard_name', 'event_guard_type', 'event_guard_enabled']
    list_filter = ['event_guard_type', 'event_guard_enabled']
    search_fields = ['event_guard_name']
