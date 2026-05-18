from rest_framework import serializers
from .models import Emergency

class EmergencySerializer(serializers.ModelSerializer):
    class Meta:
        model = Emergency
        fields = '__all__'
        read_only_fields = ['emergency_uuid', 'insert_date', 'insert_user', 'update_date', 'update_user']
