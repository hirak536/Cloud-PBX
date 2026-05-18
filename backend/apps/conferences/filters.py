import django_filters
from .models import (
    ConferenceProfile,
    Conference,
    ConferenceCenter,
    ConferenceControl,
)


class ConferenceProfileFilter(django_filters.FilterSet):
    domain = django_filters.UUIDFilter(field_name='domain__domain_uuid')
    conference_profile_name = django_filters.CharFilter(lookup_expr='icontains')
    enabled = django_filters.BooleanFilter()

    class Meta:
        model = ConferenceProfile
        fields = ['domain', 'conference_profile_name', 'enabled']


class ConferenceFilter(django_filters.FilterSet):
    domain = django_filters.UUIDFilter(field_name='domain__domain_uuid')
    domain_name = django_filters.CharFilter(field_name='domain__domain_name', lookup_expr='icontains')
    conference_name = django_filters.CharFilter(lookup_expr='icontains')
    conference_extension = django_filters.CharFilter(lookup_expr='icontains')
    conference_enabled = django_filters.BooleanFilter()
    conference_record = django_filters.BooleanFilter()
    conference_profile = django_filters.UUIDFilter(
        field_name='conference_profile__conference_profile_uuid'
    )

    class Meta:
        model = Conference
        fields = [
            'domain',
            'domain_name',
            'conference_name',
            'conference_extension',
            'conference_enabled',
            'conference_record',
            'conference_profile',
        ]


class ConferenceCenterFilter(django_filters.FilterSet):
    domain = django_filters.UUIDFilter(field_name='domain__domain_uuid')
    conference_center_name = django_filters.CharFilter(lookup_expr='icontains')
    conference_center_enabled = django_filters.BooleanFilter()

    class Meta:
        model = ConferenceCenter
        fields = ['domain', 'conference_center_name', 'conference_center_enabled']


class ConferenceControlFilter(django_filters.FilterSet):
    domain = django_filters.UUIDFilter(field_name='domain__domain_uuid')
    conference_control_name = django_filters.CharFilter(lookup_expr='icontains')
    conference_control_enabled = django_filters.BooleanFilter()

    class Meta:
        model = ConferenceControl
        fields = ['domain', 'conference_control_name', 'conference_control_enabled']
