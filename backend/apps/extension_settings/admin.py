from django.contrib import admin
from .models import ExtensionSetting

@admin.register(ExtensionSetting)
class ExtensionSettingAdmin(admin.ModelAdmin):
    list_display = ['extension_uuid', 'extension_setting_name', 'extension_setting_value', 'extension_setting_enabled']
    list_filter = ['extension_setting_enabled', 'extension_setting_category']
    search_fields = ['extension_setting_name']
