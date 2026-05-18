import django_filters

from .models import TimeCondition, TimeConditionSetting


class TimeConditionFilter(django_filters.FilterSet):
    """FilterSet for the TimeCondition model."""

    time_condition_name = django_filters.CharFilter(
        field_name='time_condition_name',
        lookup_expr='icontains',
        label='Name (contains)',
    )
    time_condition_extension = django_filters.CharFilter(
        field_name='time_condition_extension',
        lookup_expr='icontains',
        label='Extension (contains)',
    )
    time_condition_context = django_filters.CharFilter(
        field_name='time_condition_context',
        lookup_expr='iexact',
        label='Context (exact, case-insensitive)',
    )
    time_condition_enabled = django_filters.BooleanFilter(
        field_name='time_condition_enabled',
        label='Enabled',
    )
    domain = django_filters.UUIDFilter(
        field_name='domain__domain_uuid',
        label='Domain UUID',
    )

    class Meta:
        model = TimeCondition
        fields = [
            'time_condition_name',
            'time_condition_extension',
            'time_condition_context',
            'time_condition_enabled',
            'domain',
        ]


class TimeConditionSettingFilter(django_filters.FilterSet):
    """FilterSet for the TimeConditionSetting model."""

    time_condition = django_filters.UUIDFilter(
        field_name='time_condition__time_condition_uuid',
        label='TimeCondition UUID',
    )

    class Meta:
        model = TimeConditionSetting
        fields = ['time_condition']
