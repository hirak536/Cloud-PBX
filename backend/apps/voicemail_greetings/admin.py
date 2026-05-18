from django.contrib import admin
from .models import VoicemailGreeting

@admin.register(VoicemailGreeting)
class VoicemailGreetingAdmin(admin.ModelAdmin):
    list_display = ['voicemail_id', 'greeting_name', 'greeting_filename', 'insert_date']
    list_filter = ['domain']
    search_fields = ['voicemail_id', 'greeting_name']
