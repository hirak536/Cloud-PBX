from rest_framework import serializers
from .models import CallParkingSlot


class CallParkingSlotSerializer(serializers.ModelSerializer):
    domain_name = serializers.CharField(source='domain.domain_name', read_only=True)
    tenant_code = serializers.CharField(source='tenant.tenant_code', read_only=True)

    class Meta:
        model = CallParkingSlot
        fields = '__all__'
        read_only_fields = [
            'call_parking_slot_uuid', 'domain', 'tenant',
            'insert_date', 'update_date',
        ]

    def validate(self, data):
        from apps.common.extension_conflict import check_extension_conflict
        tenant = (data.get('tenant')
                  or getattr(self.instance, 'tenant', None)
                  or self.context.get('tenant'))
        slot_number = data.get('slot_number', getattr(self.instance, 'slot_number', None))
        if slot_number is not None and tenant:
            conflicts = check_extension_conflict(slot_number, tenant, exclude_model=CallParkingSlot)
            if conflicts:
                raise serializers.ValidationError({'slot_number': conflicts[0]})
        return data


class CallParkingSlotListSerializer(serializers.ModelSerializer):
    class Meta:
        model = CallParkingSlot
        fields = [
            'call_parking_slot_uuid',
            'slot_number',
            'slot_name',
            'parking_timeout',
            'timeout_action',
            'music_on_hold',
            'slot_enabled',
        ]


class BulkCreateSerializer(serializers.Serializer):
    slot_start = serializers.IntegerField()
    slot_end = serializers.IntegerField()
    parking_timeout = serializers.IntegerField(default=60)
    timeout_action = serializers.ChoiceField(
        choices=['hangup', 'return_to_parker', 'voicemail'],
        default='hangup',
    )
    timeout_voicemail_extension = serializers.CharField(default='', allow_blank=True)
    music_on_hold = serializers.CharField(default='', allow_blank=True)
    slot_enabled = serializers.BooleanField(default=True)

    def validate(self, data):
        if data['slot_start'] > data['slot_end']:
            raise serializers.ValidationError('slot_start must be <= slot_end.')
        if data['slot_end'] - data['slot_start'] > 99:
            raise serializers.ValidationError('Range cannot exceed 100 slots.')
        return data
