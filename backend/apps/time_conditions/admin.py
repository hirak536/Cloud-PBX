from django.contrib import admin
from .models import TimeCondition, TimeConditionRange

class TimeConditionRangeInline(admin.TabularInline):
    model = TimeConditionRange
    extra = 1

@admin.register(TimeCondition)
class TimeConditionAdmin(admin.ModelAdmin):
    list_display = ['dialplan_name', 'dialplan_extension', 'dialplan_enabled']
    list_filter = ['dialplan_enabled']
    search_fields = ['dialplan_name']
    inlines = [TimeConditionRangeInline]
