from django.contrib import admin
from .models import SofiaGlobalSetting

@admin.register(SofiaGlobalSetting)
class SofiaGlobalSettingAdmin(admin.ModelAdmin):
    list_display = ['sofia_global_setting_name', 'sofia_global_setting_value', 'sofia_global_setting_enabled']
    list_filter = ['sofia_global_setting_enabled']
    search_fields = ['sofia_global_setting_name']
