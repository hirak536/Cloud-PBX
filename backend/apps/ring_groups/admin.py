from django.contrib import admin
from .models import RingGroup, RingGroupDestination

class RingGroupDestinationInline(admin.TabularInline):
    model = RingGroupDestination
    extra = 0

@admin.register(RingGroup)
class RingGroupAdmin(admin.ModelAdmin):
    list_display = ['ring_group_name', 'ring_group_extension', 'ring_group_strategy', 'ring_group_enabled']
    list_filter = ['ring_group_enabled', 'ring_group_strategy', 'domain']
    search_fields = ['ring_group_name', 'ring_group_extension']
    inlines = [RingGroupDestinationInline]
