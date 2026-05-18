import django_filters
from .models import Extension, ExtensionUser


class ExtensionFilter(django_filters.FilterSet):
    """FilterSet for the Extension model.

    Supports filtering by the most commonly queried fields.
    All char filters use case-insensitive containment by default.
    """

    extension = django_filters.CharFilter(
        field_name='extension',
        lookup_expr='icontains',
        label='Extension number (contains)',
    )
    number_alias = django_filters.CharFilter(
        field_name='number_alias',
        lookup_expr='icontains',
        label='Number alias (contains)',
    )
    call_group = django_filters.CharFilter(
        field_name='call_group',
        lookup_expr='icontains',
        label='Call group (contains)',
    )
    user_context = django_filters.CharFilter(
        field_name='user_context',
        lookup_expr='iexact',
        label='SIP context (exact, case-insensitive)',
    )
    enabled = django_filters.BooleanFilter(
        field_name='enabled',
        label='Enabled',
    )
    voicemail_enabled = django_filters.BooleanFilter(
        field_name='voicemail_enabled',
        label='Voicemail enabled',
    )
    effective_caller_id_name = django_filters.CharFilter(
        field_name='effective_caller_id_name',
        lookup_expr='icontains',
        label='Effective caller-ID name (contains)',
    )
    effective_caller_id_number = django_filters.CharFilter(
        field_name='effective_caller_id_number',
        lookup_expr='icontains',
        label='Effective caller-ID number (contains)',
    )
    forward_all_enabled = django_filters.BooleanFilter(
        field_name='forward_all_enabled',
        label='Unconditional forwarding enabled',
    )
    accountcode = django_filters.CharFilter(
        field_name='accountcode',
        lookup_expr='icontains',
        label='Account code (contains)',
    )

    class Meta:
        model = Extension
        fields = [
            'extension',
            'number_alias',
            'call_group',
            'user_context',
            'enabled',
            'voicemail_enabled',
            'effective_caller_id_name',
            'effective_caller_id_number',
            'forward_all_enabled',
            'accountcode',
        ]


class ExtensionUserFilter(django_filters.FilterSet):
    extension = django_filters.UUIDFilter(field_name='extension__extension_uuid')
    user = django_filters.UUIDFilter(field_name='user__user_uuid')

    class Meta:
        model = ExtensionUser
        fields = ['extension', 'user']
