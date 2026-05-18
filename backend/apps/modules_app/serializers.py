from rest_framework import serializers
from .models import Module

class ModuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Module
        fields = '__all__'
        read_only_fields = ['module_uuid', 'insert_date', 'update_date']
