from rest_framework import serializers
from .models import PinNumber

class PinNumberSerializer(serializers.ModelSerializer):
    class Meta:
        model = PinNumber
        fields = '__all__'
        read_only_fields = ['pin_number_uuid', 'insert_date', 'insert_user', 'update_date', 'update_user']
        extra_kwargs = {'pin_number': {'write_only': True}}
