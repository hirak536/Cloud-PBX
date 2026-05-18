from rest_framework import serializers
from .models import VoicemailGreeting

class VoicemailGreetingSerializer(serializers.ModelSerializer):
    class Meta:
        model = VoicemailGreeting
        fields = '__all__'
        read_only_fields = ['voicemail_greeting_uuid', 'insert_date', 'insert_user']
