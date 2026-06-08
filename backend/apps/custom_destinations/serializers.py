from rest_framework import serializers
from .models import CustomDestination, CallerExtensionAffinity


class CustomDestinationSerializer(serializers.ModelSerializer):
    tenant_code = serializers.CharField(source='tenant.tenant_code', read_only=True)
    dest_type_display = serializers.CharField(source='get_dest_type_display', read_only=True)

    class Meta:
        model = CustomDestination
        fields = '__all__'
        read_only_fields = [
            'custom_destination_uuid', 'domain', 'tenant',
            'insert_date', 'update_date',
        ]


class CallerExtensionAffinitySerializer(serializers.ModelSerializer):
    class Meta:
        model = CallerExtensionAffinity
        fields = [
            'affinity_uuid', 'caller_number', 'extension_number',
            'last_seen', 'source', 'insert_date', 'update_date',
        ]
        read_only_fields = fields


class CustomDestinationListSerializer(serializers.ModelSerializer):
    dest_type_display = serializers.CharField(source='get_dest_type_display', read_only=True)

    class Meta:
        model = CustomDestination
        fields = [
            'custom_destination_uuid',
            'name',
            'description',
            'kind',
            'dest_type',
            'dest_type_display',
            'dest_target_uuid',
            'dest_external_number',
            'callback_to_last_caller',
            'enabled',
            'toggle_extension',
            'toggle_feature_code',
            'toggle_default_on',
            'toggle_state',
            'toggle_on_dest',
            'toggle_off_dest',
        ]
