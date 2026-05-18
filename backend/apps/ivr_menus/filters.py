import django_filters

from .models import IvrMenu, IvrMenuOption


class IvrMenuFilter(django_filters.FilterSet):
    """FilterSet for the IvrMenu model."""

    ivr_menu_name = django_filters.CharFilter(
        field_name='ivr_menu_name',
        lookup_expr='icontains',
        label='IVR menu name (contains)',
    )
    ivr_menu_extension = django_filters.CharFilter(
        field_name='ivr_menu_extension',
        lookup_expr='icontains',
        label='Extension (contains)',
    )
    ivr_menu_context = django_filters.CharFilter(
        field_name='ivr_menu_context',
        lookup_expr='iexact',
        label='Context (exact, case-insensitive)',
    )
    ivr_menu_enabled = django_filters.BooleanFilter(
        field_name='ivr_menu_enabled',
        label='Enabled',
    )
    ivr_menu_direct_dial = django_filters.BooleanFilter(
        field_name='ivr_menu_direct_dial',
        label='Direct dial enabled',
    )
    domain = django_filters.UUIDFilter(
        field_name='domain__domain_uuid',
        label='Domain UUID',
    )

    class Meta:
        model = IvrMenu
        fields = [
            'ivr_menu_name',
            'ivr_menu_extension',
            'ivr_menu_context',
            'ivr_menu_enabled',
            'ivr_menu_direct_dial',
            'domain',
        ]


class IvrMenuOptionFilter(django_filters.FilterSet):
    """FilterSet for the IvrMenuOption model."""

    ivr_menu = django_filters.UUIDFilter(
        field_name='ivr_menu__ivr_menu_uuid',
        label='IVR Menu UUID',
    )
    ivr_menu_option_action = django_filters.CharFilter(
        field_name='ivr_menu_option_action',
        lookup_expr='icontains',
        label='Action (contains)',
    )
    ivr_menu_option_digits = django_filters.CharFilter(
        field_name='ivr_menu_option_digits',
        lookup_expr='exact',
        label='Digits (exact)',
    )

    class Meta:
        model = IvrMenuOption
        fields = [
            'ivr_menu',
            'ivr_menu_option_action',
            'ivr_menu_option_digits',
        ]
