from rest_framework import serializers
from .models import Variable

class VariableSerializer(serializers.ModelSerializer):
    class Meta:
        model = Variable
        fields = '__all__'
        read_only_fields = ['variable_uuid', 'insert_date', 'insert_user', 'update_date', 'update_user']
