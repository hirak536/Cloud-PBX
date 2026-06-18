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
        """The 'flow+' presence identity a phone BLF key subscribes to.

        A bare '<ext>@domain' presence cannot light a virtual lamp — FreeSWITCH
        renders any unregistered entity as closed. So we use the FusionPBX
        'flow+' feature-code proto, served by scripts/blf_subscribe.lua, which
        DOES light. Phone programs BLF value 'flow+*<ext>' (e.g. flow+*800).
        """
        return f'flow+*{self._flow_code}@{self._domain_name}'

    @property
    def _domain_name(self):
        return self.domain.domain_name if self.domain_id else ''

    @property
    def _flow_code(self):
        """Tenant-suffixed feature code, e.g. '800-IHDT', for multi-tenant
        isolation (mirrors how extensions/parking suffix the tenant code).
        Falls back to the bare extension when the toggle has no tenant."""
        code = self.tenant.tenant_code if self.tenant_id else None
        return f'{self.toggle_extension}-{code}' if code else self.toggle_extension

    @property
    def toggle_flow_state_key(self):
        """mod_db key blf_subscribe.lua reads to decide the lamp state."""
        return f'call_flow_status/*{self._flow_code}@{self._domain_name}'

    def push_toggle_state(self):
        """Write self.toggle_state into FreeSWITCH and republish the BLF lamp.

        Uses the FusionPBX 'flow+' proto (blf_subscribe.lua) — the only
        mechanism proven to light a virtual BLF on this platform. Lamp polarity:
        we want ON=green (unlit), OFF=red (lit), so we publish 'confirmed' (lit)
        when OFF and 'terminated' (unlit) when ON — i.e. light when NOT on.
        Returns True on success, False if ESL is unavailable.
        """
        if self.kind != 'toggle' or not self.toggle_extension:
            return False
        import logging
        log = logging.getLogger(__name__)
        val = 'true' if self.toggle_state else 'false'
        try:
            from esl.client import get_esl_client
            esl = get_esl_client()
            # 1. routing state (unchanged) + the flow-proto state the Lua reads.
            esl.api(f'db insert/{self.toggle_db_key}/{val}')
            esl.api(f'db insert/{self.toggle_flow_state_key}/{val}')
            # 2. Re-publish the lamp by firing a PRESENCE_PROBE, which the running
            #    blf_subscribe.lua answers using the SAME path as the phone's
            #    initial subscribe — the only publish that actually reaches the
            #    phone. A direct PRESENCE_IN from here does NOT generate a NOTIFY
            #    (the subscription is owned by the flow proto), which is why the
            #    lamp only updated on first subscribe before. The Lua reads the
            #    mod_db key we just wrote and publishes the correct colour.
            pid = self.toggle_presence_id
            esl.sendevent('PRESENCE_PROBE', {
                'proto': 'flow',
                'from': pid,
                'to': pid,
                'expires': '3600',
                'event_type': 'presence',
            })
            return True
        except Exception as exc:
            log.warning('push_toggle_state failed for %s: %s', self.custom_destination_uuid, exc)
            return False


class ToggleEvent(models.Model):
    """Audit log of toggle (BLF switch) state changes.

    These flips are intentionally kept OUT of the call CDR (they are not real
    calls). Instead each ON/OFF change is recorded here and surfaced on the
    custom destination page, so there is a separate history of who/what flipped
    a toggle and when.
    """
    SOURCE_CHOICES = [
        ('blf',  'Phone BLF key'),
        ('ui',   'Web UI'),
        ('api',  'API'),
        ('dialplan', 'Dialplan'),
        ('resync', 'Resync'),
    ]
    toggle_event_uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    custom_destination = models.ForeignKey(
        CustomDestination,
        on_delete=models.CASCADE,
        db_column='custom_destination_uuid',
        related_name='toggle_events',
    )
    tenant = models.ForeignKey(
        'core.Tenant', on_delete=models.CASCADE, null=True, blank=True,
        db_column='tenant_uuid', related_name='toggle_events',
    )
    new_state = models.BooleanField(help_text='True = ON, False = OFF after the flip.')
    source = models.CharField(max_length=16, choices=SOURCE_CHOICES, default='ui')
    # Who/what triggered it, when known (extension number, username, or caller id).
    actor = models.CharField(max_length=128, blank=True, default='')
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'v_custom_destination_toggle_events'
        ordering = ['-created']
        indexes = [models.Index(fields=['custom_destination', '-created'])]

    def __str__(self):
        return f'{self.custom_destination_id} → {"ON" if self.new_state else "OFF"} ({self.source})'


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
        help_text='outbound | manual_seed | manual_ui — where this mapping came from.')

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
