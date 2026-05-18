from rest_framework import serializers
from .models import Recording, CallRecording

class RecordingSerializer(serializers.ModelSerializer):
    class Meta:
        model = Recording
        fields = '__all__'
        read_only_fields = ['recording_uuid', 'insert_date', 'insert_user', 'update_date', 'update_user']

class CallRecordingSerializer(serializers.ModelSerializer):
    class Meta:
        model = CallRecording
        fields = '__all__'
        read_only_fields = ['call_recording_uuid', 'insert_date']
