from django.contrib import admin
from .models import Destination, DEST_TYPE_CHOICES


@admin.register(Destination)
class DestinationAdmin(admin.ModelAdmin):
    list_display = [
        'destination_number', 'dest_type', 'fax', 'destination_enabled',
        'tenant', 'domain', 'destination_record',
    ]
    list_filter = ['dest_type', 'destination_enabled', 'destination_record', 'domain', 'tenant']
    search_fields = ['destination_number', 'dest_external_number', 'destination_description']
    fieldsets = [
        ('DID — Inbound Phone Number', {
            'fields': ['tenant', 'domain', 'destination_number', 'destination_number_regex'],
            'description': (
                'The phone number your SIP provider sends calls to. '
                'Use the exact number as your provider sends it (e.g. +15551002000 or 5551002000). '
                'Regex is optional — leave blank to match the number exactly.'
            ),
        }),
        ('Destination — Where the call goes', {
            'fields': ['dest_type', 'dest_target_uuid', 'dest_external_number', 'fax'],
            'description': (
                'Select Destination type, then paste the UUID of the target from its admin page. '
                'For External Number, fill in the phone number field instead of a UUID. '
                'To enable fax, select a Fax box: use dest_type=Fax for fax-only DIDs, '
                'or keep voice dest_type and select a Fax box to enable CNG auto-detection '
                '(shared voice+fax on same number).'
            ),
        }),
        ('Call Options', {
            'fields': [
                'destination_cid_name_prefix',
                'destination_ringback',
                'destination_hold_music',
                'destination_record',
                'destination_accountcode',
            ],
            'classes': ['collapse'],
        }),
        ('Status', {
            'fields': ['destination_enabled', 'destination_description'],
        }),
    ]

    def get_readonly_fields(self, request, obj=None):
        # dest_target_uuid is shown as a UUID input — guidance is in the description
        return []
