import uuid
from django.db import models
from core.models import Domain


DEST_TYPE_CHOICES = [
    ('extension',           'Extension'),
    ('ivr_menu',            'IVR Menu'),
    ('ring_group',          'Ring Group'),
    ('voicemail',           'Voicemail'),
    ('time_condition',      'Time Condition'),
    ('working_hours',       'Working Hours'),
    ('call_flow',           'Call Flow'),
    ('conference',          'Conference'),
    ('external',            'External Number'),
    ('call_forward',        'Call Forward'),
    ('fax',                 'Fax (direct fax receive)'),
    ('hangup',              'Hangup'),
    ('custom_destination',  'Custom Destination'),
    ('call_park',           'Call Park'),
]

ALWAYS_RECORD_CHOICES = [
    ('',         'No'),
    ('all',      'All'),
    ('local',    'Local'),
    ('outbound', 'Outbound'),
    ('inbound',  'Inbound'),
]

FAX_PROTOCOL_CHOICES = [
    ('t38_only',        'T.38 Only'),
    ('t38_preferred',   'T.38 Preferred'),
    ('sdp_passthrough', 'SDP Passthrough'),
    ('none',            'None'),
]


class Destination(models.Model):
    """
    DID (Direct Inward Dialing) — inbound phone number routing.

    Each record stores one DID and where calls to that number should go.
    dest_type + dest_target_uuid resolve the actual FreeSWITCH dialplan action.
    """
    destination_uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        'core.Tenant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column='tenant_uuid',
        related_name='%(app_label)s_%(class)s_set',
    )
    domain = models.ForeignKey(
        Domain,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        db_column='domain_uuid',
        related_name='destinations',
    )

    # ── Identity ──────────────────────────────────────────────────────────
    destination_name = models.CharField(
        max_length=128, blank=True, default='',
        help_text='Friendly name for this DID, e.g. "IHS Main".',
    )

    # ── DID (the inbound phone number) ────────────────────────────────────
    destination_number = models.CharField(
        max_length=64,
        help_text='DID / inbound phone number, e.g. +15551002000 or 5551002000.',
    )
    destination_number_regex = models.CharField(
        max_length=255, blank=True, default='',
        help_text='Optional regex override. Leave blank to match the number exactly.',
    )

    # ── Capacity / caller ID flags ─────────────────────────────────────────
    max_channels = models.IntegerField(
        null=True, blank=True,
        help_text='Maximum simultaneous inbound calls. Null = unlimited.',
    )
    notify_over_limit = models.BooleanField(default=False)
    use_cnam_service = models.BooleanField(default=False)
    hide_callerid = models.BooleanField(default=False)
    use_as_emergency_callerid = models.BooleanField(default=False)
    inbound_call_rate = models.CharField(
        max_length=64, blank=True, default='',
        help_text='Per-minute rate applied to inbound calls. Leave blank = not applied.',
    )

    # ── Where the call goes ───────────────────────────────────────────────
    dest_type = models.CharField(
        max_length=32,
        choices=DEST_TYPE_CHOICES,
        blank=True, default='',
        verbose_name='Destination type (synced from first action)',
    )
    dest_target_uuid = models.UUIDField(
        null=True, blank=True,
        verbose_name='Destination target',
        help_text='UUID of the Extension / IVR / Ring Group / etc. selected above.',
    )
    dest_external_number = models.CharField(
        max_length=64, blank=True, default='',
        verbose_name='External number',
        help_text='Phone number to bridge to (only used when Destination type = External Number).',
    )
    fax = models.ForeignKey(
        'fax.Fax',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        db_column='fax_uuid',
        related_name='destinations',
        verbose_name='Fax box',
        help_text=(
            'Link a fax box for two use cases: '
            '(1) Set Destination type = "Fax" to route all calls directly to this fax box. '
            '(2) Set any other Destination type + select a Fax box here to enable CNG '
            'auto-detection — voice calls route normally, fax calls auto-switch to the fax box.'
        ),
    )

    # ── Voice / recording settings ────────────────────────────────────────
    unconditional_forward = models.BooleanField(default=False)
    always_record = models.CharField(
        max_length=16, blank=True, default='',
        choices=ALWAYS_RECORD_CHOICES,
        help_text='Record calls arriving on this DID.',
    )
    email_recording_to = models.EmailField(blank=True, default='')
    transcript_recorded = models.BooleanField(default=False)
    summarize_recorded = models.BooleanField(default=False)
    sentiment_analysis = models.BooleanField(default=False)

    # ── Caller ID manipulation ─────────────────────────────────────────────
    destination_cid_number_prefix = models.CharField(
        max_length=64, blank=True, default='',
        verbose_name='Caller ID number prefix',
        help_text='Text prepended to inbound caller ID number.',
    )
    destination_cid_name_prefix = models.CharField(
        max_length=64, blank=True, default='',
        verbose_name='Caller ID name prefix',
        help_text='Text prepended to inbound caller ID name, e.g. "Sales: ".',
    )
    destination_ringback = models.CharField(
        max_length=255, blank=True, default='',
        help_text='Ringback tone URI, e.g. %(2000,4000,440,480) or us-ring.',
    )
    destination_hold_music = models.CharField(
        max_length=255, blank=True, default='',
        help_text='Hold music URI. Leave blank to use system default.',
    )
    destination_record = models.BooleanField(
        default=False,
        help_text='Legacy record flag (superseded by always_record).',
    )
    destination_accountcode = models.CharField(
        max_length=64, blank=True, default='',
        help_text='Accountcode / billing code for CDR.',
    )
    callback_to_last_caller = models.BooleanField(
        default=False,
        help_text='If enabled, route the inbound call to the last extension that called this caller\'s number.',
    )

    # ── Fax (inline per-DID settings) ─────────────────────────────────────
    fax_receive = models.BooleanField(default=False)
    fax_station_id = models.CharField(max_length=128, blank=True, default='')
    fax_header = models.CharField(max_length=255, blank=True, default='')
    fax_protocol = models.CharField(
        max_length=32, blank=True, default='t38_only',
        choices=FAX_PROTOCOL_CHOICES,
    )
    fax_email_destinations = models.CharField(
        max_length=255, blank=True, default='',
        help_text='Comma-separated email addresses to send received faxes to.',
    )
    fax_store = models.BooleanField(default=False)
    fax_on_receive = models.CharField(max_length=64, blank=True, default='')

    # ── Status ────────────────────────────────────────────────────────────
    destination_enabled = models.BooleanField(default=True)
    destination_description = models.TextField(blank=True, default='')

    insert_date = models.DateTimeField(auto_now_add=True)
    insert_user = models.UUIDField(null=True, blank=True)
    update_date = models.DateTimeField(auto_now=True)
    update_user = models.UUIDField(null=True, blank=True)

    class Meta:
        db_table = 'v_destinations'
        ordering = ['destination_number']
        constraints = [
            models.UniqueConstraint(fields=['destination_number'], name='unique_destination_number'),
        ]
        indexes = [
            models.Index(fields=['destination_number']),
            models.Index(fields=['tenant', 'destination_number']),
            models.Index(fields=['destination_enabled']),
        ]

    def __str__(self):
        label = self.destination_name or self.destination_number
        return f'{label} → {self.get_dest_type_display()}'


class DestinationAction(models.Model):
    """
    Ordered routing action for a DID.

    A DID can have multiple actions tried in priority order, e.g.:
    1 → Extension 1001, 2 → Ring Group, 3 → Voicemail.
    """
    destination_action_uuid = models.UUIDField(
        primary_key=True, default=uuid.uuid4, editable=False,
    )
    destination = models.ForeignKey(
        Destination,
        on_delete=models.CASCADE,
        related_name='actions',
        db_column='destination_uuid',
    )
    dest_type = models.CharField(max_length=32, choices=DEST_TYPE_CHOICES)
    dest_target_uuid = models.UUIDField(null=True, blank=True)
    dest_external_number = models.CharField(max_length=64, blank=True, default='')
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        db_table = 'v_destination_actions'
        ordering = ['order']

    def __str__(self):
        return f'{self.get_dest_type_display()} (order {self.order})'
