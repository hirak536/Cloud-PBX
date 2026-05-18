import django_filters
from .models import MusicOnHold


class MusicOnHoldFilter(django_filters.FilterSet):
    domain = django_filters.UUIDFilter(field_name='domain__domain_uuid')
    domain_name = django_filters.CharFilter(
        field_name='domain__domain_name', lookup_expr='icontains'
    )
    music_on_hold_name = django_filters.CharFilter(lookup_expr='icontains')
    music_on_hold_rate = django_filters.CharFilter(lookup_expr='iexact')
    music_on_hold_enabled = django_filters.BooleanFilter()

    class Meta:
        model = MusicOnHold
        fields = [
            'domain',
            'domain_name',
            'music_on_hold_name',
            'music_on_hold_rate',
            'music_on_hold_enabled',
        ]
