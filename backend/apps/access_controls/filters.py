import django_filters

from .models import AccessControl, AccessControlNode


class AccessControlFilter(django_filters.FilterSet):
    """FilterSet for the AccessControl model."""

    access_control_name = django_filters.CharFilter(
        field_name='access_control_name',
        lookup_expr='icontains',
        label='Name (contains)',
    )
    default_action = django_filters.ChoiceFilter(
        field_name='default_action',
        choices=AccessControl.DEFAULT_ACTION_CHOICES,
        label='Default action',
    )
    enabled = django_filters.BooleanFilter(
        field_name='enabled',
        label='Enabled',
    )
    domain = django_filters.UUIDFilter(
        field_name='domain__domain_uuid',
        label='Domain UUID',
    )

    class Meta:
        model = AccessControl
        fields = [
            'access_control_name',
            'default_action',
            'enabled',
            'domain',
        ]


class AccessControlNodeFilter(django_filters.FilterSet):
    """FilterSet for the AccessControlNode model."""

    access_control = django_filters.UUIDFilter(
        field_name='access_control__access_control_uuid',
        label='AccessControl UUID',
    )
    node_type = django_filters.ChoiceFilter(
        field_name='node_type',
        choices=AccessControlNode.TYPE_CHOICES,
        label='Node type',
    )
    node_cidr = django_filters.CharFilter(
        field_name='node_cidr',
        lookup_expr='icontains',
        label='CIDR (contains)',
    )
    enabled = django_filters.BooleanFilter(
        field_name='enabled',
        label='Enabled',
    )

    class Meta:
        model = AccessControlNode
        fields = [
            'access_control',
            'node_type',
            'node_cidr',
            'enabled',
        ]
