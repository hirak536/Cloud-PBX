from rest_framework import serializers
from .models import OutboundRoute


class OutboundRouteSerializer(serializers.ModelSerializer):
    gateway_name = serializers.CharField(source='gateway.gateway', read_only=True)
    gateway_2_name = serializers.CharField(source='gateway_2.gateway', read_only=True, default=None)
    gateway_3_name = serializers.CharField(source='gateway_3.gateway', read_only=True, default=None)

    class Meta:
        model = OutboundRoute
        fields = '__all__'
        read_only_fields = ['outbound_route_uuid', 'insert_date', 'update_date']
        validators = []

    def validate(self, data):
        name = data.get('outbound_route_name', getattr(self.instance, 'outbound_route_name', None))
        qs = OutboundRoute.objects.filter(outbound_route_name=name)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError(
                {'outbound_route_name': 'An outbound route with this name already exists.'}
            )
        return data


class OutboundRouteListSerializer(serializers.ModelSerializer):
    """Lightweight list serializer."""
    gateway_name = serializers.CharField(source='gateway.gateway', read_only=True)
    gateway_2_name = serializers.CharField(source='gateway_2.gateway', read_only=True, default=None)
    gateway_3_name = serializers.CharField(source='gateway_3.gateway', read_only=True, default=None)

    class Meta:
        model = OutboundRoute
        fields = [
            'outbound_route_uuid',
            'outbound_route_name',
            'outbound_route_order',
            'dialplan_pattern',
            'prepend',
            'gateway',
            'gateway_name',
            'gateway_2',
            'gateway_2_name',
            'gateway_3',
            'gateway_3_name',
            'caller_id_number',
            'caller_id_name',
            'outbound_route_enabled',
            'outbound_route_description',
        ]
