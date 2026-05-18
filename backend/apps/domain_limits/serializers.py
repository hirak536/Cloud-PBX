from rest_framework import serializers
from .models import DomainLimit

class DomainLimitSerializer(serializers.ModelSerializer):
    class Meta:
        model = DomainLimit
        fields = '__all__'
        read_only_fields = ['domain_limit_uuid', 'insert_date', 'insert_user', 'update_date', 'update_user']
