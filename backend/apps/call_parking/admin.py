from django.contrib import admin
from .models import CallParkingSlot


@admin.register(CallParkingSlot)
class CallParkingSlotAdmin(admin.ModelAdmin):
    list_display = ['slot_number', 'slot_name', 'parking_timeout', 'timeout_action', 'slot_enabled', 'tenant']
    list_filter = ['slot_enabled', 'tenant']
    search_fields = ['slot_name']
    ordering = ['slot_number']
