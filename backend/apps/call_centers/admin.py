from django.contrib import admin
from .models import CallCenter, CallCenterAgent, CallCenterTier

class CallCenterTierInline(admin.TabularInline):
    model = CallCenterTier
    extra = 0

@admin.register(CallCenter)
class CallCenterAdmin(admin.ModelAdmin):
    list_display = ['queue_name', 'domain', 'strategy', 'enabled']
    list_filter = ['enabled', 'strategy', 'domain']
    search_fields = ['queue_name']
    inlines = [CallCenterTierInline]

@admin.register(CallCenterAgent)
class CallCenterAgentAdmin(admin.ModelAdmin):
    list_display = ['agent_name', 'domain', 'agent_type', 'agent_status', 'enabled']
    list_filter = ['enabled', 'agent_type', 'agent_status', 'domain']
    search_fields = ['agent_name', 'agent_contact']
