from rest_framework import serializers
from .models import RingGroup, RingGroupDestination


class RingGroupDestinationSerializer(serializers.ModelSerializer):
    class Meta:
        model = RingGroupDestination
        fields = '__all__'
        read_only_fields = ['ring_group_destination_uuid', 'ring_group', 'domain', 'tenant', 'insert_date']


class RingGroupSerializer(serializers.ModelSerializer):
    destinations = RingGroupDestinationSerializer(many=True, required=False)
    domain_name = serializers.CharField(source='domain.domain_name', read_only=True)
    tenant_code = serializers.CharField(source='tenant.tenant_code', read_only=True)

    class Meta:
        model = RingGroup
        fields = '__all__'
        read_only_fields = ['ring_group_uuid', 'domain', 'tenant', 'insert_date', 'update_date']

    def _save_destinations(self, instance, destinations_data):
        instance.destinations.all().delete()
        for dest in destinations_data:
            dest.pop('ring_group_destination_uuid', None)
            dest.pop('ring_group', None)
            dest.pop('insert_date', None)
            RingGroupDestination.objects.create(
                ring_group=instance,
                tenant=instance.tenant,
                domain=instance.domain,
                **dest,
            )

    def validate(self, data):
        from apps.common.extension_conflict import check_extension_conflict
        from .models import RingGroup
        tenant = (data.get('tenant')
                  or getattr(self.instance, 'tenant', None)
                  or self.context.get('tenant'))
        ext = data.get('ring_group_extension', getattr(self.instance, 'ring_group_extension', None))
        if ext and tenant:
            conflicts = check_extension_conflict(ext, tenant, exclude_model=RingGroup)
            if conflicts:
                raise serializers.ValidationError({'ring_group_extension': conflicts[0]})
        return data

    def create(self, validated_data):
        destinations_data = validated_data.pop('destinations', [])
        instance = super().create(validated_data)
        self._save_destinations(instance, destinations_data)
        return instance

    def update(self, instance, validated_data):
        destinations_data = validated_data.pop('destinations', None)
        instance = super().update(instance, validated_data)
        if destinations_data is not None:
            self._save_destinations(instance, destinations_data)
        return instance


class RingGroupListSerializer(serializers.ModelSerializer):
    destinations = RingGroupDestinationSerializer(many=True, read_only=True)

    class Meta:
        model = RingGroup
        fields = [
            'ring_group_uuid',
            'ring_group_name',
            'ring_group_extension',
            'ring_group_strategy',
            'ring_group_call_timeout',
            'ring_group_enabled',
            'destinations',
        ]
