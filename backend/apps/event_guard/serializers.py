from rest_framework import serializers
from .models import EventGuard

class EventGuardSerializer(serializers.ModelSerializer):
    class Meta:
        model = EventGuard
        fields = '__all__'
        read_only_fields = ['event_guard_uuid', 'insert_date', 'insert_user', 'update_date', 'update_user']
