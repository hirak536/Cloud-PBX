import django_filters

from .models import FeatureCode


class FeatureCodeFilter(django_filters.FilterSet):
    """FilterSet for the FeatureCode model."""

    feature_code_label = django_filters.CharFilter(
        field_name='feature_code_label',
        lookup_expr='icontains',
        label='Label (contains)',
    )
    feature_code = django_filters.CharFilter(
        field_name='feature_code',
        lookup_expr='icontains',
        label='Feature code (contains)',
    )
    feature_code_context = django_filters.CharFilter(
        field_name='feature_code_context',
        lookup_expr='iexact',
        label='Context (exact, case-insensitive)',
    )
    feature_code_type = django_filters.CharFilter(
        field_name='feature_code_type',
        lookup_expr='iexact',
        label='Type (exact, case-insensitive)',
    )
    feature_code_enabled = django_filters.BooleanFilter(
        field_name='feature_code_enabled',
        label='Enabled',
    )
    domain = django_filters.UUIDFilter(
        field_name='domain__domain_uuid',
        label='Domain UUID',
    )

    class Meta:
        model = FeatureCode
        fields = [
            'feature_code_label',
            'feature_code',
            'feature_code_context',
            'feature_code_type',
            'feature_code_enabled',
            'domain',
        ]
