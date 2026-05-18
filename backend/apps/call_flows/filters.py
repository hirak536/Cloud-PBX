import django_filters

from .models import CallFlow


class CallFlowFilter(django_filters.FilterSet):
    """FilterSet for the CallFlow model."""

    call_flow_name = django_filters.CharFilter(
        field_name='call_flow_name',
        lookup_expr='icontains',
        label='Call flow name (contains)',
    )
    call_flow_extension = django_filters.CharFilter(
        field_name='call_flow_extension',
        lookup_expr='icontains',
        label='Extension (contains)',
    )
    call_flow_feature_code = django_filters.CharFilter(
        field_name='call_flow_feature_code',
        lookup_expr='icontains',
        label='Feature code (contains)',
    )
    call_flow_status = django_filters.CharFilter(
        field_name='call_flow_status',
        lookup_expr='exact',
        label='Status (true/false)',
    )
    call_flow_context = django_filters.CharFilter(
        field_name='call_flow_context',
        lookup_expr='iexact',
        label='Context (exact, case-insensitive)',
    )
    call_flow_enabled = django_filters.BooleanFilter(
        field_name='call_flow_enabled',
        label='Enabled',
    )
    domain = django_filters.UUIDFilter(
        field_name='domain__domain_uuid',
        label='Domain UUID',
    )

    class Meta:
        model = CallFlow
        fields = [
            'call_flow_name',
            'call_flow_extension',
            'call_flow_feature_code',
            'call_flow_status',
            'call_flow_context',
            'call_flow_enabled',
            'domain',
        ]
