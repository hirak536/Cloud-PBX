import django_filters
from .models import Dialplan, DialplanDetail


class DialplanFilter(django_filters.FilterSet):
    dialplan_name = django_filters.CharFilter(
        field_name='dialplan_name',
        lookup_expr='icontains',
        label='Name (contains)',
    )
    dialplan_number = django_filters.CharFilter(
        field_name='dialplan_number',
        lookup_expr='icontains',
        label='Number/pattern (contains)',
    )
    dialplan_context = django_filters.CharFilter(
        field_name='dialplan_context',
        lookup_expr='iexact',
        label='Context (exact, case-insensitive)',
    )
    dialplan_enabled = django_filters.BooleanFilter(
        field_name='dialplan_enabled',
        label='Enabled',
    )
    dialplan_global = django_filters.BooleanFilter(
        field_name='dialplan_global',
        label='Global (not domain-scoped)',
    )
    dialplan_destination = django_filters.BooleanFilter(
        field_name='dialplan_destination',
        label='Is an inbound destination',
    )
    dialplan_order_min = django_filters.NumberFilter(
        field_name='dialplan_order',
        lookup_expr='gte',
        label='Order >= (min)',
    )
    dialplan_order_max = django_filters.NumberFilter(
        field_name='dialplan_order',
        lookup_expr='lte',
        label='Order <= (max)',
    )

    class Meta:
        model = Dialplan
        fields = [
            'dialplan_name',
            'dialplan_number',
            'dialplan_context',
            'dialplan_enabled',
            'dialplan_global',
            'dialplan_destination',
        ]


class DialplanDetailFilter(django_filters.FilterSet):
    dialplan = django_filters.UUIDFilter(field_name='dialplan__dialplan_uuid')
    dialplan_detail_tag = django_filters.ChoiceFilter(
        field_name='dialplan_detail_tag',
        choices=DialplanDetail.TAG_CHOICES,
    )
    dialplan_detail_group = django_filters.NumberFilter(field_name='dialplan_detail_group')

    class Meta:
        model = DialplanDetail
        fields = ['dialplan', 'dialplan_detail_tag', 'dialplan_detail_group']
