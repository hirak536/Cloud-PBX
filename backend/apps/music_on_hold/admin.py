from django.contrib import admin
from .models import MusicOnHold

@admin.register(MusicOnHold)
class MusicOnHoldAdmin(admin.ModelAdmin):
    list_display = ['music_on_hold_name', 'music_on_hold_rate', 'music_on_hold_path']
    search_fields = ['music_on_hold_name']
