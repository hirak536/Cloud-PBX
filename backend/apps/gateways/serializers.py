from rest_framework import serializers
from .models import Gateway


class GatewaySerializer(serializers.ModelSerializer):
    domain_name = serializers.CharField(source='domain.domain_name', read_only=True)
    tenant_code = serializers.CharField(source='tenant.tenant_code', read_only=True)

    class Meta:
        model = Gateway
        fields = '__all__'
        read_only_fields = ['gateway_uuid', 'insert_date', 'update_date']
        extra_kwargs = {
            'password': {'write_only': True, 'required': False, 'allow_blank': True},
        }
        # Suppress UniqueTogetherValidator for (tenant, gateway) — same as
        # Extension/OutboundRoute: DRF requires tenant even when nullable.
        # Uniqueness is checked manually below.
        validators = []

    def validate(self, data):
        gateway = data.get('gateway', getattr(self.instance, 'gateway', None))
        qs = Gateway.objects.filter(gateway=gateway)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError(
                {'gateway': 'A gateway with this name already exists.'}
            )
        return data

    def update(self, instance, validated_data):
        # Don't blank out the password if it wasn't sent
        password = validated_data.pop('password', None)
        instance = super().update(instance, validated_data)
        if password:
            instance.password = password
            instance.save(update_fields=['password'])
        return instance
