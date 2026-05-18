from rest_framework import serializers
from .models import CallBroadcast, CallBroadcastContact

class CallBroadcastContactSerializer(serializers.ModelSerializer):
    class Meta:
        model = CallBroadcastContact
        fields = '__all__'
        read_only_fields = ['call_broadcast_contact_uuid', 'insert_date']

class CallBroadcastSerializer(serializers.ModelSerializer):
    contacts = CallBroadcastContactSerializer(many=True, read_only=True)

    class Meta:
        model = CallBroadcast
        fields = '__all__'
        read_only_fields = ['call_broadcast_uuid', 'insert_date', 'insert_user', 'update_date', 'update_user']
