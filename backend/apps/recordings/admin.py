from django.contrib import admin
from .models import Recording, CallRecording

@admin.register(Recording)
class RecordingAdmin(admin.ModelAdmin):
    list_display = ['recording_name', 'recording_filename', 'insert_date']
    search_fields = ['recording_name', 'recording_filename']

@admin.register(CallRecording)
class CallRecordingAdmin(admin.ModelAdmin):
    list_display = ['call_recording_caller_id_number', 'call_recording_destination_number',
                    'call_recording_duration', 'call_recording_start_stamp']
    list_filter = ['domain']
