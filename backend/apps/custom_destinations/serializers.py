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


class CallerExtensionAffinityWriteSerializer(serializers.Serializer):
    """Validates manual create/update of a caller→extension mapping.

    caller_number is normalized (last 10 US digits) by the view via
    affinity.normalize_number; extension is the dialable extension, with any
    tenant suffix (e.g. "432-GMD") accepted and passed through to the router,
    which strips it. Both are required and non-empty.
    """
    caller_number = serializers.CharField(max_length=32)
    extension_number = serializers.CharField(max_length=32)

    def validate_extension_number(self, v):
        v = (v or '').strip()
        if not v:
            raise serializers.ValidationError('Extension is required.')
        return v


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
            'toggle_on_type',
            'toggle_on_target_uuid',
            'toggle_on_external',
            'toggle_off_type',
            'toggle_off_target_uuid',
            'toggle_off_external',
        ]
