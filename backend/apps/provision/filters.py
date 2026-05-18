import django_filters
from .models import ProvisionTemplate


class ProvisionTemplateFilter(django_filters.FilterSet):
    vendor = django_filters.CharFilter(field_name='vendor', lookup_expr='icontains')
    model = django_filters.CharFilter(field_name='model', lookup_expr='icontains')
    firmware_version = django_filters.CharFilter(field_name='firmware_version', lookup_expr='icontains')
    template_name = django_filters.CharFilter(field_name='template_name', lookup_expr='icontains')
    content_type = django_filters.CharFilter(field_name='content_type', lookup_expr='iexact')
    is_active = django_filters.BooleanFilter(field_name='is_active')

    class Meta:
        model = ProvisionTemplate
        fields = [
            'vendor',
            'model',
            'firmware_version',
            'template_name',
            'content_type',
            'is_active',
        ]
