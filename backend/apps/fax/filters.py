import django_filters
from .models import Fax, FaxQueue


class FaxFilter(django_filters.FilterSet):
    domain = django_filters.UUIDFilter(field_name='domain__domain_uuid')
    domain_name = django_filters.CharFilter(field_name='domain__domain_name', lookup_expr='icontains')
    fax_name = django_filters.CharFilter(lookup_expr='icontains')
    fax_extension = django_filters.CharFilter(lookup_expr='icontains')
    fax_email = django_filters.CharFilter(lookup_expr='icontains')
    fax_enabled = django_filters.BooleanFilter()

    class Meta:
        model = Fax
        fields = ['domain', 'domain_name', 'fax_name', 'fax_extension', 'fax_email', 'fax_enabled']


class FaxQueueFilter(django_filters.FilterSet):
    domain = django_filters.UUIDFilter(field_name='domain__domain_uuid')
    fax = django_filters.UUIDFilter(field_name='fax__fax_uuid')
    fax_status = django_filters.ChoiceFilter(choices=FaxQueue.STATUS_CHOICES)
    fax_destination_number = django_filters.CharFilter(lookup_expr='icontains')
    insert_date_after = django_filters.DateTimeFilter(field_name='insert_date', lookup_expr='gte')
    insert_date_before = django_filters.DateTimeFilter(field_name='insert_date', lookup_expr='lte')

    class Meta:
        model = FaxQueue
        fields = [
            'domain',
            'fax',
            'fax_status',
            'fax_destination_number',
            'insert_date_after',
            'insert_date_before',
        ]
