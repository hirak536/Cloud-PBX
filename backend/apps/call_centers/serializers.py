from rest_framework import serializers
from .models import CallCenter, CallCenterAgent, CallCenterTier


class CallCenterTierSerializer(serializers.ModelSerializer):
    class Meta:
        model = CallCenterTier
        fields = '__all__'
        read_only_fields = ['tier_uuid']


class CallCenterSerializer(serializers.ModelSerializer):
    tiers = CallCenterTierSerializer(many=True, read_only=True)
    domain_name = serializers.CharField(source='domain.domain_name', read_only=True)
    tenant_code = serializers.CharField(source='tenant.tenant_code', read_only=True)

    class Meta:
        model = CallCenter
        fields = '__all__'
        read_only_fields = ['queue_uuid', 'domain', 'tenant', 'insert_date', 'update_date']


class CallCenterAgentSerializer(serializers.ModelSerializer):
    domain_name = serializers.CharField(source='domain.domain_name', read_only=True)
    tenant_code = serializers.CharField(source='tenant.tenant_code', read_only=True)

    class Meta:
        model = CallCenterAgent
        fields = '__all__'
        read_only_fields = ['agent_uuid', 'domain', 'tenant', 'insert_date', 'update_date']
