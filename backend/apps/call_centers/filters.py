import django_filters
from .models import CallCenter, CallCenterAgent, CallCenterTier


class CallCenterFilter(django_filters.FilterSet):
    domain = django_filters.UUIDFilter(field_name='domain__domain_uuid')
    domain_name = django_filters.CharFilter(field_name='domain__domain_name', lookup_expr='icontains')
    queue_name = django_filters.CharFilter(lookup_expr='icontains')
    queue_extension = django_filters.CharFilter(lookup_expr='icontains')
    strategy = django_filters.ChoiceFilter(choices=CallCenter.STRATEGY_CHOICES)
    enabled = django_filters.BooleanFilter()

    class Meta:
        model = CallCenter
        fields = [
            'domain',
            'domain_name',
            'queue_name',
            'queue_extension',
            'strategy',
            'enabled',
        ]


class CallCenterAgentFilter(django_filters.FilterSet):
    domain = django_filters.UUIDFilter(field_name='domain__domain_uuid')
    domain_name = django_filters.CharFilter(field_name='domain__domain_name', lookup_expr='icontains')
    agent_name = django_filters.CharFilter(lookup_expr='icontains')
    agent_type = django_filters.ChoiceFilter(choices=CallCenterAgent.AGENT_TYPE_CHOICES)
    agent_status = django_filters.CharFilter(lookup_expr='icontains')
    enabled = django_filters.BooleanFilter()

    class Meta:
        model = CallCenterAgent
        fields = [
            'domain',
            'domain_name',
            'agent_name',
            'agent_type',
            'agent_status',
            'enabled',
        ]


class CallCenterTierFilter(django_filters.FilterSet):
    domain = django_filters.UUIDFilter(field_name='domain__domain_uuid')
    call_center = django_filters.UUIDFilter(field_name='call_center__queue_uuid')
    agent = django_filters.UUIDFilter(field_name='agent__agent_uuid')
    tier_level = django_filters.NumberFilter()

    class Meta:
        model = CallCenterTier
        fields = ['domain', 'call_center', 'agent', 'tier_level']
