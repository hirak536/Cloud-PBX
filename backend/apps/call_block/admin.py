from django.contrib import admin
from .models import CallBlock

@admin.register(CallBlock)
class CallBlockAdmin(admin.ModelAdmin):
    list_display = ['call_block_number', 'call_block_action', 'call_block_enabled']
    list_filter = ['call_block_action', 'call_block_enabled']
    search_fields = ['call_block_number']
