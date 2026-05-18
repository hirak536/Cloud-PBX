from django.contrib import admin
from .models import SipProfile, SipProfileSetting, SipProfileDomain

class SipProfileSettingInline(admin.TabularInline):
    model = SipProfileSetting
    extra = 0

class SipProfileDomainInline(admin.TabularInline):
    model = SipProfileDomain
    extra = 0

@admin.register(SipProfile)
class SipProfileAdmin(admin.ModelAdmin):
    list_display = ['sip_profile_name', 'sip_profile_hostname', 'sip_profile_enabled']
    list_filter = ['sip_profile_enabled']
    search_fields = ['sip_profile_name']
    inlines = [SipProfileSettingInline, SipProfileDomainInline]
