from rest_framework import serializers
from .models import Dialplan, DialplanDetail


class DialplanDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = DialplanDetail
        fields = '__all__'
        read_only_fields = ['dialplan_detail_uuid', 'insert_date']


class DialplanSerializer(serializers.ModelSerializer):
    details = DialplanDetailSerializer(many=True, read_only=True)
    domain_name = serializers.CharField(source='domain.domain_name', read_only=True)
    tenant_code = serializers.CharField(source='tenant.tenant_code', read_only=True)

    class Meta:
        model = Dialplan
        fields = '__all__'
        read_only_fields = ['dialplan_uuid', 'insert_date', 'update_date']


class DialplanListSerializer(serializers.ModelSerializer):
    domain_name = serializers.CharField(source='domain.domain_name', read_only=True)
    tenant_code = serializers.CharField(source='tenant.tenant_code', read_only=True)

    class Meta:
        model = Dialplan
        fields = ['dialplan_uuid', 'dialplan_name', 'dialplan_number', 'dialplan_context',
                  'dialplan_order', 'dialplan_enabled', 'dialplan_global', 'domain_name',
                  'tenant_code']
