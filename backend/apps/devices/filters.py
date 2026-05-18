import django_filters
from .models import Device, DeviceLine, DeviceProfile, DeviceProfileSetting, DeviceSetting


class DeviceFilter(django_filters.FilterSet):
    device_label = django_filters.CharFilter(field_name='device_label', lookup_expr='icontains')
    device_mac_address = django_filters.CharFilter(field_name='device_mac_address', lookup_expr='icontains')
    device_vendor = django_filters.CharFilter(field_name='device_vendor', lookup_expr='icontains')
    device_model = django_filters.CharFilter(field_name='device_model', lookup_expr='icontains')
    device_enabled = django_filters.BooleanFilter(field_name='device_enabled')
    domain = django_filters.UUIDFilter(field_name='domain__domain_uuid')
    user = django_filters.UUIDFilter(field_name='user__user_uuid')
    device_profile = django_filters.UUIDFilter(field_name='device_profile__device_profile_uuid')
    provisioned_after = django_filters.DateTimeFilter(
        field_name='device_provisioned_date', lookup_expr='gte',
        label='Provisioned after (datetime)',
    )
    provisioned_before = django_filters.DateTimeFilter(
        field_name='device_provisioned_date', lookup_expr='lte',
        label='Provisioned before (datetime)',
    )

    class Meta:
        model = Device
        fields = [
            'device_label',
            'device_mac_address',
            'device_vendor',
            'device_model',
            'device_enabled',
            'domain',
            'user',
            'device_profile',
        ]


class DeviceSettingFilter(django_filters.FilterSet):
    device = django_filters.UUIDFilter(field_name='device__device_uuid')
    domain = django_filters.UUIDFilter(field_name='domain__domain_uuid')
    device_setting_name = django_filters.CharFilter(field_name='device_setting_name', lookup_expr='icontains')
    device_setting_enabled = django_filters.BooleanFilter(field_name='device_setting_enabled')

    class Meta:
        model = DeviceSetting
        fields = ['device', 'domain', 'device_setting_name', 'device_setting_enabled']


class DeviceLineFilter(django_filters.FilterSet):
    device = django_filters.UUIDFilter(field_name='device__device_uuid')
    domain = django_filters.UUIDFilter(field_name='domain__domain_uuid')
    enabled = django_filters.BooleanFilter(field_name='enabled')
    line_number = django_filters.NumberFilter(field_name='line_number')

    class Meta:
        model = DeviceLine
        fields = ['device', 'domain', 'enabled', 'line_number']


class DeviceProfileFilter(django_filters.FilterSet):
    device_profile_name = django_filters.CharFilter(field_name='device_profile_name', lookup_expr='icontains')
    device_profile_enabled = django_filters.BooleanFilter(field_name='device_profile_enabled')
    domain = django_filters.UUIDFilter(field_name='domain__domain_uuid')

    class Meta:
        model = DeviceProfile
        fields = ['device_profile_name', 'device_profile_enabled', 'domain']


class DeviceProfileSettingFilter(django_filters.FilterSet):
    device_profile = django_filters.UUIDFilter(field_name='device_profile__device_profile_uuid')
    domain = django_filters.UUIDFilter(field_name='domain__domain_uuid')
    device_profile_setting_category = django_filters.CharFilter(
        field_name='device_profile_setting_category', lookup_expr='icontains'
    )
    device_profile_setting_enabled = django_filters.BooleanFilter(field_name='device_profile_setting_enabled')

    class Meta:
        model = DeviceProfileSetting
        fields = [
            'device_profile',
            'domain',
            'device_profile_setting_category',
            'device_profile_setting_enabled',
        ]
