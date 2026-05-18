from django.contrib import admin
from .models import CallFlow, CallFlowOption

class CallFlowOptionInline(admin.TabularInline):
    model = CallFlowOption
    extra = 1

@admin.register(CallFlow)
class CallFlowAdmin(admin.ModelAdmin):
    list_display = ['call_flow_name', 'call_flow_extension', 'call_flow_status', 'call_flow_enabled']
    list_filter = ['call_flow_enabled']
    search_fields = ['call_flow_name']
    inlines = [CallFlowOptionInline]
