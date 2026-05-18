from rest_framework import serializers
from .models import Fifo, FifoCallers

class FifoCallersSerializer(serializers.ModelSerializer):
    class Meta:
        model = FifoCallers
        fields = '__all__'
        read_only_fields = ['fifo_caller_uuid', 'insert_date']

class FifoSerializer(serializers.ModelSerializer):
    callers = FifoCallersSerializer(many=True, read_only=True)

    class Meta:
        model = Fifo
        fields = '__all__'
        read_only_fields = ['fifo_uuid', 'insert_date', 'insert_user', 'update_date', 'update_user']

class FifoListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Fifo
        fields = ['fifo_uuid', 'fifo_name', 'fifo_extension', 'fifo_strategy', 'fifo_enabled']
