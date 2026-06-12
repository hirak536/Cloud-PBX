import uuid
import random
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from core.models import Domain, User
from core.validators import validate_multi_email


class Extension(models.Model):
    extension_uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
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
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column='domain_uuid',
        related_name='extensions',
    )
    extension = models.CharField(max_length=32)
    sip_username = models.CharField(
        max_length=64, blank=True, default='', db_index=True,
        help_text='Auto-generated SIP username: extension-tenant_code (e.g. 1001-ACM).',
    )
    number_alias = models.CharField(max_length=32, blank=True, default='')
    password = models.CharField(max_length=128)
    accountcode = models.CharField(max_length=32, blank=True, default='')
    effective_caller_id_name = models.CharField(max_length=128, blank=True, default='')
    effective_caller_id_number = models.CharField(max_length=32, blank=True, default='')
    outbound_caller_id_name = models.CharField(max_length=128, blank=True, default='')
    outbound_caller_id_number = models.CharField(max_length=32, blank=True, default='')
    emergency_caller_id_name = models.CharField(max_length=128, blank=True, default='')
    emergency_caller_id_number = models.CharField(max_length=32, blank=True, default='')
    directory_full_name = models.CharField(max_length=256, blank=True, default='')
    directory_visible = models.BooleanField(default=True)
    directory_exten_visible = models.BooleanField(default=True)
    limit_max = models.IntegerField(default=0)
    limit_destination = models.CharField(max_length=256, blank=True, default='')
    call_timeout = models.IntegerField(default=30)
    reject_to_voicemail = models.BooleanField(
        default=False,
        help_text='Immediately route to voicemail when any registered device rejects the call.'
    )
    call_group = models.CharField(max_length=32, blank=True, default='')
    call_screen_enabled = models.BooleanField(default=False)
    user_record = models.CharField(max_length=32, blank=True, default='',
        choices=[('','Disabled'),('all','All'),('local','Local'),('outbound','Outbound'),('inbound','Inbound')])
    voicemail_enabled = models.BooleanField(default=True)
    voicemail_id = models.CharField(max_length=32, blank=True, default='')
    voicemail_password = models.CharField(max_length=32, blank=True, default='')
    voicemail_mail_to = models.CharField(
        max_length=512, blank=True, default='',
        validators=[validate_multi_email],
        help_text='One or more email addresses, separated by commas.')
    voicemail_file = models.CharField(max_length=32, default='attach',
        choices=[('attach','Attach'),('link','Link'),('none','None')])
    voicemail_local_after_email = models.BooleanField(default=True)
    # Additional Destinations (call forwarding) — master toggle
    call_forward_active = models.BooleanField(
        default=False,
        help_text='Enable additional destinations. All forwarding rules below are active only when this is checked.',
    )
    # Unconditional
    forward_all_enabled = models.BooleanField(default=False)
    forward_all_destination = models.CharField(max_length=64, blank=True, default='')
    # On No Answer
    forward_no_answer_enabled = models.BooleanField(default=False)
    forward_no_answer_destination = models.CharField(max_length=64, blank=True, default='')
    # On Extension Busy
    forward_busy_enabled = models.BooleanField(default=False)
    forward_busy_destination = models.CharField(max_length=64, blank=True, default='')
    # On Extension Offline
    forward_user_not_registered_enabled = models.BooleanField(default=False)
    forward_user_not_registered_destination = models.CharField(max_length=64, blank=True, default='')
    # On Condition
    forward_on_condition_enabled = models.BooleanField(default=False)
    forward_on_condition = models.CharField(
        max_length=256, blank=True, default='',
        help_text='Dialplan condition expression (e.g. ${caller_id_number} == 1234).',
    )
    forward_on_condition_destination = models.CharField(max_length=64, blank=True, default='')
    user_context = models.CharField(max_length=128, default='default')
    toll_allow = models.CharField(max_length=256, blank=True, default='')
    auth_acl = models.CharField(max_length=256, blank=True, default='')
    cidr = models.CharField(max_length=256, blank=True, default='')
    sip_force_contact = models.CharField(max_length=32, blank=True, default='')
    sip_force_expires = models.IntegerField(null=True, blank=True)
    max_registrations = models.IntegerField(default=0)
    CODEC_CHOICES = [
        # ── CORE_PCM_MODULE (always available) ──────────────────────────────
        ('PCMU',        'PCMU — G.711 u-law (built-in)'),
        ('PCMA',        'PCMA — G.711 a-law (built-in)'),
        # ── CORE_SPEEX_MODULE (always available) ─────────────────────────────
        ('speex',       'Speex (built-in)'),
        # ── CORE_VPX_MODULE (always available) ───────────────────────────────
        ('VP8',         'VP8 Video (built-in)'),
        ('VP9',         'VP9 Video (built-in)'),
        # ── mod_spandsp ───────────────────────────────────────────────────────
        ('G722',        'G.722 — HD Voice (mod_spandsp)'),
        ('G726-16',     'G.726 16k (mod_spandsp)'),
        ('G726-24',     'G.726 24k (mod_spandsp)'),
        ('G726-32',     'G.726 32k (mod_spandsp)'),
        ('G726-40',     'G.726 40k (mod_spandsp)'),
        ('GSM',         'GSM (mod_spandsp)'),
        ('ADPCM',       'ADPCM IMA (mod_spandsp)'),
        ('LPC',         'LPC-10 (mod_spandsp)'),
        # ── mod_opus ──────────────────────────────────────────────────────────
        ('OPUS',        'OPUS — Wideband (mod_opus)'),
        # ── mod_g729 ──────────────────────────────────────────────────────────
        ('G729',        'G.729 (mod_g729 — license required)'),
        # ── mod_g723_1 ────────────────────────────────────────────────────────
        ('G7231',       'G.723.1 6.3k (mod_g723_1)'),
        # ── mod_amr ───────────────────────────────────────────────────────────
        ('AMR',         'AMR — Bandwidth Efficient (mod_amr)'),
        ('AMR-WB',      'AMR — Octet Aligned (mod_amr)'),
        # ── mod_av (video) ────────────────────────────────────────────────────
        ('H263',        'H.263 Video (mod_av)'),
        ('H263-1998',   'H.263+ Video (mod_av)'),
        ('H264',        'H.264 Video (mod_av)'),
    ]
    codec_preference = models.CharField(
        max_length=256, blank=True, default='',
        help_text='Comma-separated codec list e.g. PCMU,PCMA,G722. PCMU,PCMA always safe. G729 needs license.',
    )
    absolute_codec_string = models.CharField(max_length=256, blank=True, default='')
    force_ping = models.BooleanField(default=False)
    sip_bypass_media = models.CharField(
        max_length=32, blank=True, default='',
        choices=[
            ('', 'Disabled — FreeSWITCH in RTP path (default)'),
            ('true', 'Bypass Media — direct RTP between endpoints'),
            ('proxy', 'Proxy Media — FS forwards RTP without processing'),
        ],
        help_text=(
            'Media mode for UDP/TCP/TLS calls. '
            'Bypass: FreeSWITCH exits the RTP path. '
            'Proxy: FS stays in path but only forwards, no re-encoding.'
        ),
    )
    sip_bypass_media_webrtc = models.CharField(
        max_length=32, blank=True, default='',
        choices=[
            ('', 'Normal — FreeSWITCH in RTP path (default, required for WebRTC)'),
            ('proxy', 'Proxy Media — FS forwards only'),
        ],
        help_text=(
            'Media mode for WebRTC (WSS) calls. '
            'Bypass is not available for WebRTC as it is incompatible with DTLS-SRTP.'
        ),
    )
    hold_music = models.CharField(max_length=256, blank=True, default='')
    # ── Transport / WebRTC ────────────────────────────────────────────────
    transport = models.CharField(
        max_length=16, blank=True, default='any',
        choices=[
            ('any',  'Any (UDP, TCP, TLS and WebRTC)'),
            ('udp',  'UDP only'),
            ('tcp',  'TCP only'),
            ('tls',  'TLS only'),
            ('wss',  'WebRTC (WSS) only'),
        ],
        help_text='Allowed SIP transport for this extension.',
    )
    webrtc_support = models.BooleanField(
        default=False,
        help_text='Enable WebRTC-specific params (SRTP, WSS transport) in directory XML.',
    )
    rtp_encryption = models.BooleanField(
        default=False,
        help_text='Require SRTP for RTP encryption.',
    )
    mobile_push_enabled = models.BooleanField(default=False)
    # ── Outbound DID (caller ID source) ──────────────────────────────────
    outbound_did = models.ForeignKey(
        'destinations.Destination',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column='outbound_did_uuid',
        related_name='outbound_extensions',
        verbose_name='Outbound caller ID (DID)',
        help_text='DID whose number is used as the outbound caller ID for this extension.',
    )
    # ── Outbound calling ──────────────────────────────────────────────────
    outbound_route = models.ForeignKey(
        'gateways.Gateway',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column='gateway_uuid',
        related_name='extensions',
        verbose_name='Default outbound route',
        help_text='Default SIP trunk/gateway for outbound calls from this extension.',
    )
    outbound_xheader_name = models.CharField(
        max_length=64, blank=True, default='',
        verbose_name='Custom X-header name',
        help_text='SIP X-header name sent on outbound calls, e.g. X-Tenant-ID. Must start with X-.',
    )
    outbound_xheader_value = models.CharField(
        max_length=256, blank=True, default='',
        verbose_name='Custom X-header value',
        help_text='Value for the custom SIP X-header above.',
    )
    mwi_account = models.CharField(max_length=256, blank=True, default='')
    language = models.CharField(max_length=16, blank=True, default='')
    enabled = models.BooleanField(default=True)
    description = models.TextField(blank=True, default='')
    insert_date = models.DateTimeField(auto_now_add=True, null=True)
    insert_user = models.UUIDField(null=True, blank=True)
    update_date = models.DateTimeField(auto_now=True, null=True)
    update_user = models.UUIDField(null=True, blank=True)

    class Meta:
        db_table = 'v_extensions'
        unique_together = [('tenant', 'extension')]
        ordering = ['extension']

    def save(self, *args, **kwargs):
        tenant_code = ''
        if self.tenant_id:
            try:
                tenant_code = self.tenant.tenant_code
            except Exception:
                pass
        self.sip_username = f'{self.extension}-{tenant_code}' if tenant_code else self.extension

        # Sync outbound caller ID from the linked DID when set.
        if self.outbound_did_id:
            did_number = self.outbound_did.destination_number
            self.outbound_caller_id_number = did_number
            if not self.outbound_caller_id_name:
                self.outbound_caller_id_name = did_number

        # Default effective caller ID to the extension number (for internal calls).
        if not self.effective_caller_id_number:
            self.effective_caller_id_number = self.extension
        if not self.effective_caller_id_name:
            self.effective_caller_id_name = self.directory_full_name or self.extension

        # Auto-assign domain: try tenant-specific first, then any universal/enabled domain.
        # A single domain (e.g. 10.127.127.76) can be shared across all tenants.
        if not self.domain_id:
            domain = (
                (self.tenant.domains.filter(domain_enabled=True).first() if self.tenant_id else None)
                or Domain.objects.filter(domain_universal=True, domain_enabled=True).first()
                or Domain.objects.filter(domain_enabled=True).first()
            )
            if domain:
                self.domain = domain

        super().save(*args, **kwargs)

    def __str__(self):
        domain_name = self.domain.domain_name if self.domain_id else '?'
        return f'{self.sip_username or self.extension}@{domain_name}'


class ExtensionUser(models.Model):
    extension_user_uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        'core.Tenant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column='tenant_uuid',
        related_name='%(app_label)s_%(class)s_set',
    )
    domain = models.ForeignKey(Domain, on_delete=models.SET_NULL, null=True, blank=True, db_column='domain_uuid')
    extension = models.ForeignKey(Extension, on_delete=models.CASCADE,
                                  db_column='extension_uuid', related_name='extension_users')
    user = models.ForeignKey(User, on_delete=models.CASCADE, db_column='user_uuid',
                             to_field='user_uuid', related_name='extension_users')
    insert_date = models.DateTimeField(auto_now_add=True, null=True)

    class Meta:
        db_table = 'v_extension_users'
        unique_together = [('extension', 'user')]


@receiver(post_save, sender=Extension)
def auto_create_voicemail(sender, instance, created, **kwargs):
    """Create a Voicemail box when an Extension is saved with voicemail_enabled=True.

    PIN defaults to a random 4-digit number (never the extension password).
    Leave voicemail_password blank on the box to allow PIN-less access.
    """
    if not instance.voicemail_enabled:
        return
    from apps.voicemails.models import Voicemail
    mailbox_id = instance.voicemail_id or instance.extension
    # Generate a random 4-digit PIN for new voicemail boxes
    random_pin = str(random.randint(1000, 9999))
    # Seed the box name from the extension's display name on first create.
    # Manual edits on the Voicemail page won't be overwritten because we only
    # set this in `defaults` (applied when the row is created).
    seeded_name = instance.directory_full_name or instance.effective_caller_id_name or ''
    vm, created = Voicemail.objects.get_or_create(
        tenant=instance.tenant,
        voicemail_id=mailbox_id,
        defaults={
            'domain': instance.domain,
            'voicemail_password': random_pin,
            'voicemail_mail_to': instance.voicemail_mail_to or '',
            'voicemail_file': instance.voicemail_file or 'attach',
            'voicemail_local_after_email': instance.voicemail_local_after_email,
            'voicemail_enabled': True,
            'voicemail_description': seeded_name,
        },
    )
