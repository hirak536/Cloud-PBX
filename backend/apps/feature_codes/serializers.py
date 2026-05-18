from rest_framework import serializers
from .models import FeatureCode

class FeatureCodeSerializer(serializers.ModelSerializer):
    class Meta:
        model = FeatureCode
        fields = '__all__'
        read_only_fields = ['feature_code_uuid', 'insert_date', 'insert_user', 'update_date', 'update_user']
