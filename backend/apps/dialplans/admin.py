from django.contrib import admin
from .models import Dialplan, DialplanDetail

class DialplanDetailInline(admin.TabularInline):
    model = DialplanDetail
    extra = 0

@admin.register(Dialplan)
class DialplanAdmin(admin.ModelAdmin):
    list_display = ['dialplan_name', 'dialplan_number', 'dialplan_context', 'dialplan_order', 'dialplan_enabled']
    list_filter = ['dialplan_enabled', 'dialplan_global', 'dialplan_context']
    search_fields = ['dialplan_name', 'dialplan_number']
    inlines = [DialplanDetailInline]
