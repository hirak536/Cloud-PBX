from rest_framework import serializers
from .models import CallBlock

class CallBlockSerializer(serializers.ModelSerializer):
    class Meta:
        model = CallBlock
        fields = '__all__'
        read_only_fields = ['call_block_uuid', 'insert_date', 'insert_user', 'update_date', 'update_user']
