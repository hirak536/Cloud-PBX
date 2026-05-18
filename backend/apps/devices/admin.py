from django.contrib import admin
from .models import Device, DeviceLine, DeviceSetting

class DeviceLineInline(admin.TabularInline):
    model = DeviceLine
    extra = 1

class DeviceSettingInline(admin.TabularInline):
    model = DeviceSetting
    extra = 0

@admin.register(Device)
class DeviceAdmin(admin.ModelAdmin):
    list_display = ['device_mac_address', 'device_vendor', 'device_model', 'device_label', 'device_enabled']
    list_filter = ['device_vendor', 'device_enabled']
    search_fields = ['device_mac_address', 'device_label']
    inlines = [DeviceLineInline, DeviceSettingInline]
