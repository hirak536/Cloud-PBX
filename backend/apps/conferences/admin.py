from django.contrib import admin
from .models import Conference, ConferenceProfile, ConferenceProfileSetting

class ConferenceProfileSettingInline(admin.TabularInline):
    model = ConferenceProfileSetting
    extra = 0

@admin.register(ConferenceProfile)
class ConferenceProfileAdmin(admin.ModelAdmin):
    list_display = ['conference_profile_name', 'enabled']
    inlines = [ConferenceProfileSettingInline]

@admin.register(Conference)
class ConferenceAdmin(admin.ModelAdmin):
    list_display = ['conference_name', 'conference_extension', 'domain', 'conference_max_members', 'conference_enabled']
    list_filter = ['conference_enabled', 'conference_record', 'domain']
    search_fields = ['conference_name', 'conference_extension']
