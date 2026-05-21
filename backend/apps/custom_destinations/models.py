import uuid
from django.db import models
from core.models import Domain


DEST_TYPE_CHOICES = [
    ('extension',       'Extension'),
    ('ivr_menu',        'IVR Menu'),
    ('ring_group',      'Ring Group'),
    ('voicemail',       'Voicemail'),
    ('time_condition',  'Time Condition'),
    ('working_hours',   'Working Hours'),
    ('call_flow',       'Call Flow'),
    ('conference',      'Conference'),
    ('external',        'External Number'),
    ('call_forward',    'Call Forward'),
    ('fax',             'Fax'),
    ('hangup',          'Hangup'),
]


KIND_CHOICES = [
    ('simple',            'Simple Destination'),
    ('sticky_last_agent', 'Route to Last Agent'),
    # Future kinds (time_of_day, area_code_routing, round_robin, ...) plug in here
    # and the frontend renders matching fields via the kind registry.
]


class CustomDestination(models.Model):
    """
    A reusable named destination preset.

    Defines a named shortcut (e.g. "After Hours Voicemail", "Main IVR")
    that can be referenced from DIDs, Working Hours, Ring Group timeouts,
    and anywhere else a destination is required.

    At call-time the dialplan generator resolves this to the underlying
    dest_type + target just like any other destination.
    """
    custom_destination_uuid = models.UUIDField(
        primary_key=True, default=uuid.uuid4, editable=False,
    )
    tenant = models.ForeignKey(
        'core.Tenant',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        db_column='tenant_uuid',
        related_name='%(app_label)s_%(class)s_set',
    )
    domain = models.ForeignKey(
        Domain,
        on_delete=models.CASCADE,
        null=True, blank=True,
        db_column='domain_uuid',
        related_name='custom_destinations',
    )

    # ── Identity ──────────────────────────────────────────────────────────────
    name = models.CharField(max_length=128, help_text='Friendly name, e.g. "After Hours Voicemail".')
    description = models.TextField(blank=True, default='')

    # ── Kind ──────────────────────────────────────────────────────────────────
    kind = models.CharField(
        max_length=32, choices=KIND_CHOICES, default='simple',
        help_text='Behavior selector. "Simple" routes straight to dest_type. '
                  'Other kinds layer extra logic (e.g. sticky_last_agent looks '
                  'up the caller-extension affinity first).',
    )

    # ── Where calls go ────────────────────────────────────────────────────────
    dest_type = models.CharField(max_length=32, choices=DEST_TYPE_CHOICES)
    dest_target_uuid = models.UUIDField(
        null=True, blank=True,
        help_text='UUID of the Extension / IVR / Ring Group / etc.',
    )
    dest_external_number = models.CharField(
        max_length=64, blank=True, default='',
        help_text='External number (only used when dest_type = external).',
    )

    # ── Routing options ───────────────────────────────────────────────────────
    callback_to_last_caller = models.BooleanField(
        default=False,
        help_text='Route inbound calls to the last extension that previously called the caller\'s number.',
    )

    # ── Status ────────────────────────────────────────────────────────────────
    enabled = models.BooleanField(default=True)

    insert_date = models.DateTimeField(auto_now_add=True)
    insert_user = models.UUIDField(null=True, blank=True)
    update_date = models.DateTimeField(auto_now=True)
    update_user = models.UUIDField(null=True, blank=True)

    class Meta:
        db_table = 'v_custom_destinations'
        ordering = ['name']

    def __str__(self):
        return f'{self.name} → {self.get_dest_type_display()}'


class CallerExtensionAffinity(models.Model):
    """
    Sticky last-agent routing cache: which extension most recently dialed a
    given (DID, customer) pair. Populated by outbound XmlCdr post-save signals
    and queried by the dialplan when a DID's destination is a CustomDestination
    with callback_to_last_caller=True.
    """
    affinity_uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        'core.Tenant',
        on_delete=models.CASCADE,
        db_column='tenant_uuid',
        related_name='caller_extension_affinity',
    )
    domain = models.ForeignKey(
        Domain,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        db_column='domain_uuid',
        related_name='caller_extension_affinity',
    )
    caller_number = models.CharField(max_length=32, db_index=True,
        help_text='Normalized customer number (last 10 digits, US).')
    extension_number = models.CharField(max_length=32,
        help_text='Extension that most recently dialed this customer.')
    last_seen = models.DateTimeField(db_index=True,
        help_text='Timestamp of the most recent outbound call that set this mapping.')
    source = models.CharField(max_length=16, default='outbound',
        help_text='outbound | manual_seed — where this mapping came from.')

    insert_date = models.DateTimeField(auto_now_add=True)
    update_date = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'v_caller_extension_affinity'
        constraints = [
            models.UniqueConstraint(
                fields=['tenant', 'caller_number'],
                name='uniq_affinity_tenant_caller',
            ),
        ]
        indexes = [
            models.Index(fields=['tenant', 'caller_number']),
        ]

    def __str__(self):
        return f'{self.caller_number} → ext {self.extension_number}'
