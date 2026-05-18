import django_filters
from .models import Voicemail, VoicemailMessage


class VoicemailFilter(django_filters.FilterSet):
    voicemail_id = django_filters.CharFilter(
        field_name='voicemail_id',
        lookup_expr='icontains',
        label='Voicemail ID (contains)',
    )
    voicemail_mail_to = django_filters.CharFilter(
        field_name='voicemail_mail_to',
        lookup_expr='icontains',
        label='Email (contains)',
    )
    voicemail_enabled = django_filters.BooleanFilter(
        field_name='voicemail_enabled',
        label='Enabled',
    )
    voicemail_transcription_enabled = django_filters.BooleanFilter(
        field_name='voicemail_transcription_enabled',
        label='Transcription enabled',
    )
    voicemail_file = django_filters.ChoiceFilter(
        field_name='voicemail_file',
        choices=Voicemail._meta.get_field('voicemail_file').choices,
        label='Email attachment type',
    )

    class Meta:
        model = Voicemail
        fields = [
            'voicemail_id',
            'voicemail_mail_to',
            'voicemail_enabled',
            'voicemail_transcription_enabled',
            'voicemail_file',
        ]


class VoicemailMessageFilter(django_filters.FilterSet):
    voicemail = django_filters.UUIDFilter(field_name='voicemail__voicemail_uuid')
    message_status = django_filters.ChoiceFilter(
        field_name='message_status',
        choices=VoicemailMessage.STATUS_CHOICES,
        label='Message status',
    )
    caller_id_number = django_filters.CharFilter(
        field_name='caller_id_number',
        lookup_expr='icontains',
        label='Caller ID number (contains)',
    )
    caller_id_name = django_filters.CharFilter(
        field_name='caller_id_name',
        lookup_expr='icontains',
        label='Caller ID name (contains)',
    )
    created_after = django_filters.NumberFilter(
        field_name='created_epoch',
        lookup_expr='gte',
        label='Created after epoch (>=)',
    )
    created_before = django_filters.NumberFilter(
        field_name='created_epoch',
        lookup_expr='lte',
        label='Created before epoch (<=)',
    )

    class Meta:
        model = VoicemailMessage
        fields = [
            'voicemail',
            'message_status',
            'caller_id_number',
            'caller_id_name',
        ]
