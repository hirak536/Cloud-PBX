import django_filters
from .models import SipProfile, SipProfileSetting, SipProfileDomain


class SipProfileFilter(django_filters.FilterSet):
    sip_profile_name = django_filters.CharFilter(lookup_expr='icontains')
    sip_profile_hostname = django_filters.CharFilter(lookup_expr='icontains')
    sip_profile_enabled = django_filters.BooleanFilter()

    class Meta:
        model = SipProfile
        fields = [
            'sip_profile_name',
            'sip_profile_hostname',
            'sip_profile_enabled',
        ]


class SipProfileSettingFilter(django_filters.FilterSet):
    sip_profile = django_filters.UUIDFilter(field_name='sip_profile__sip_profile_uuid')
    sip_profile_setting_name = django_filters.CharFilter(lookup_expr='icontains')
    sip_profile_setting_enabled = django_filters.BooleanFilter()

    class Meta:
        model = SipProfileSetting
        fields = [
            'sip_profile',
            'sip_profile_setting_name',
            'sip_profile_setting_enabled',
        ]


class SipProfileDomainFilter(django_filters.FilterSet):
    sip_profile = django_filters.UUIDFilter(field_name='sip_profile__sip_profile_uuid')
    sip_profile_domain_name = django_filters.CharFilter(lookup_expr='icontains')
    sip_profile_domain_alias = django_filters.BooleanFilter()
    sip_profile_domain_parse = django_filters.BooleanFilter()

    class Meta:
        model = SipProfileDomain
        fields = [
            'sip_profile',
            'sip_profile_domain_name',
            'sip_profile_domain_alias',
            'sip_profile_domain_parse',
        ]
