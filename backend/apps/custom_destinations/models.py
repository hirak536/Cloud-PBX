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
    ('custom_destination', 'Custom Destination'),
]


KIND_CHOICES = [
    ('simple',            'Simple Destination'),
    ('sticky_last_agent', 'Route to Last Agent'),
    ('toggle',            'Toggle (BLF switch)'),
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

    # ── Toggle (BLF switch) kind ────────────────────────────────────────────────
    # When kind == 'toggle' this custom destination becomes a switch:
    #   • `toggle_extension` is a dialable number (like an extension, but BLF-only):
    #     a phone subscribes a BLF key to it to see GREEN while ON / RED while OFF,
    #     and pressing the key (dialing it) flips the state with a confirmation tone,
    #   • `toggle_feature_code` is an optional second dial string that also flips it,
    #   • calls routed *through* it go to the "ON" destination while on, "OFF" while off.
    # The two branches reference other CustomDestinations so they can be any dest type.
    toggle_extension = models.CharField(
        max_length=16, blank=True, default='',
        help_text='Dialable BLF number for this toggle, e.g. "801". Subscribe a phone '
                  'BLF key to it; dialing it flips the toggle. Required for toggle kind.',
    )
    toggle_feature_code = models.CharField(
        max_length=16, blank=True, default='',
        help_text='Optional second dial string that also flips the toggle, e.g. "*71".',
    )
    toggle_default_on = models.BooleanField(
        default=True,
        help_text='Initial state seeded into a brand-new toggle (True = ON / green).',
    )
    toggle_state = models.BooleanField(
        default=True,
        help_text='Live canonical state — the source of truth. True = ON / green, '
                  'False = OFF / red. Kept in sync with FreeSWITCH mod_db + presence; '
                  'republished to phones on reboot/resync so the lamp never drifts.',
    )
    # Legacy: ON/OFF used to reference another CustomDestination only. Kept for
    # back-compat/rollback; new code uses the toggle_on_*/toggle_off_* triples
    # below, which mirror dest_type/dest_target_uuid/dest_external_number and so
    # can route to ANY destination type (extension, IVR, ring group, voicemail,
    # external number, hangup, or another custom destination).
    toggle_on_dest = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='+',
        db_column='toggle_on_dest_uuid',
        help_text='Legacy ON-branch FK to another CustomDestination. Superseded by toggle_on_type.',
    )
    toggle_off_dest = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='+',
        db_column='toggle_off_dest_uuid',
        help_text='Legacy OFF-branch FK to another CustomDestination. Superseded by toggle_off_type.',
    )

    # ON / OFF branch destinations as a type+target triple (same shape as the
    # simple-kind dest_type/dest_target_uuid/dest_external_number). Resolved at
    # dialplan-gen time via _resolve_dest_action, so the BLF toggle can route to
    # any destination — matching the extension route dropdown.
    toggle_on_type = models.CharField(max_length=32, blank=True, default='')
    toggle_on_target_uuid = models.CharField(max_length=64, blank=True, default='')
    toggle_on_external = models.CharField(max_length=64, blank=True, default='')
    toggle_off_type = models.CharField(max_length=32, blank=True, default='')
    toggle_off_target_uuid = models.CharField(max_length=64, blank=True, default='')
    toggle_off_external = models.CharField(max_length=64, blank=True, default='')

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

    # ── Toggle state helpers ────────────────────────────────────────────────
    @property
    def toggle_db_key(self):
        """mod_db key holding this toggle's state inside FreeSWITCH."""
        return f'custom_toggle/{self.custom_destination_uuid}'

    @property
    def toggle_presence_id(self):
        """Presence identity a phone BLF key subscribes to (number@domain)."""
        domain_name = self.domain.domain_name if self.domain_id else ''
        return f'{self.toggle_extension}@{domain_name}'

    def push_toggle_state(self):
        """Write self.toggle_state into FreeSWITCH and republish presence.

        Makes the live phone lamp match the DB source of truth. Safe to call
        repeatedly (idempotent) — used on UI flips and on reboot/resync so a
        rebooted phone showing the wrong colour gets corrected.
        Returns True on success, False if ESL is unavailable (state still saved
        in the DB and will resync on the next dialplan route / resync call).
        """
        if self.kind != 'toggle' or not self.toggle_extension:
            return False
        import logging
        log = logging.getLogger(__name__)
        val = 'true' if self.toggle_state else 'false'
        # 'confirmed' lights the lamp (green/ON), 'terminated' clears it (red/OFF).
        state = 'confirmed' if self.toggle_state else 'terminated'
        status = 'Active (ON)' if self.toggle_state else 'Idle (OFF)'
        try:
            from esl.client import get_esl_client
            esl = get_esl_client()
            esl.api(f'db insert/{self.toggle_db_key}/{val}')
            esl.presence_in(self.toggle_presence_id, status=status, state=state)
            return True
        except Exception as exc:
            log.warning('push_toggle_state failed for %s: %s', self.custom_destination_uuid, exc)
            return False


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
