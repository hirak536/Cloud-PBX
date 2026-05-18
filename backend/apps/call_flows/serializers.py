from rest_framework import serializers
from .models import CallFlow, CallFlowOption

class CallFlowOptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = CallFlowOption
        fields = '__all__'
        read_only_fields = ['call_flow_option_uuid', 'insert_date']

class CallFlowSerializer(serializers.ModelSerializer):
    options = CallFlowOptionSerializer(many=True, read_only=True)

    class Meta:
        model = CallFlow
        fields = '__all__'
        read_only_fields = ['call_flow_uuid', 'insert_date', 'insert_user', 'update_date', 'update_user']

class CallFlowListSerializer(serializers.ModelSerializer):
    class Meta:
        model = CallFlow
        fields = [
            'call_flow_uuid', 'call_flow_name', 'call_flow_extension',
            'call_flow_feature_code', 'call_flow_status', 'call_flow_enabled',
            'day_dest_type', 'day_dest_target_uuid', 'day_dest_external_number',
            'night_dest_type', 'night_dest_target_uuid', 'night_dest_external_number',
        ]
