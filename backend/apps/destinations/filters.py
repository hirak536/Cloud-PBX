import django_filters

from .models import Destination


class DestinationFilter(django_filters.FilterSet):
    """FilterSet for the Destination model."""

    destination_number = django_filters.CharFilter(
        field_name='destination_number',
        lookup_expr='icontains',
        label='DID/number (contains)',
    )
    destination_type = django_filters.ChoiceFilter(
        field_name='destination_type',
        choices=Destination.DESTINATION_TYPE_CHOICES,
        label='Destination type',
    )
    destination_context = django_filters.CharFilter(
        field_name='destination_context',
        lookup_expr='iexact',
        label='Context (exact, case-insensitive)',
    )
    destination_app = django_filters.CharFilter(
        field_name='destination_app',
        lookup_expr='icontains',
        label='App (contains)',
    )
    destination_enabled = django_filters.BooleanFilter(
        field_name='destination_enabled',
        label='Enabled',
    )
    destination_record = django_filters.BooleanFilter(
        field_name='destination_record',
        label='Recording enabled',
    )
    destination_accountcode = django_filters.CharFilter(
        field_name='destination_accountcode',
        lookup_expr='icontains',
        label='Account code (contains)',
    )
    domain = django_filters.UUIDFilter(
        field_name='domain__domain_uuid',
        label='Domain UUID',
    )

    class Meta:
        model = Destination
        fields = [
            'destination_number',
            'destination_type',
            'destination_context',
            'destination_app',
            'destination_enabled',
            'destination_record',
            'destination_accountcode',
            'domain',
        ]
