from django.contrib import admin
from .models import CallBroadcast, CallBroadcastContact

class CallBroadcastContactInline(admin.TabularInline):
    model = CallBroadcastContact
    extra = 1

@admin.register(CallBroadcast)
class CallBroadcastAdmin(admin.ModelAdmin):
    list_display = ['call_broadcast_name', 'call_broadcast_caller_id_number', 'call_broadcast_enabled']
    list_filter = ['call_broadcast_enabled']
    search_fields = ['call_broadcast_name']
    inlines = [CallBroadcastContactInline]
