from rest_framework import serializers
from .models import CustomDestination


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


class CustomDestinationListSerializer(serializers.ModelSerializer):
    dest_type_display = serializers.CharField(source='get_dest_type_display', read_only=True)

    class Meta:
        model = CustomDestination
        fields = [
            'custom_destination_uuid',
            'name',
            'description',
            'dest_type',
            'dest_type_display',
            'dest_target_uuid',
            'dest_external_number',
            'callback_to_last_caller',
            'enabled',
        ]
