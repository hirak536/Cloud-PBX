import uuid
from django.db import models
from core.models import Domain


class Gateway(models.Model):
    gateway_uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        'core.Tenant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column='tenant_uuid',
        related_name='%(app_label)s_%(class)s_set',
    )
    domain = models.ForeignKey(Domain, on_delete=models.CASCADE, null=True, blank=True,
                               db_column='domain_uuid', related_name='gateways')
    TRUNK_TYPE_CHOICES = [
        ('register', 'Register — PBX registers to provider (username/password)'),
        ('account',  'Account — Digest auth on outbound, no registration'),
        ('peer',     'Peer — IP-based auth, no credentials required'),
    ]
    trunk_type = models.CharField(
        max_length=16,
        choices=TRUNK_TYPE_CHOICES,
        default='register',
        help_text='How FreeSWITCH authenticates with this trunk.',
    )
    gateway = models.CharField(max_length=128)
    username = models.CharField(max_length=128, blank=True, default='')
    password = models.CharField(max_length=128, blank=True, default='')
    distinct_to = models.BooleanField(default=False)
    auth_username = models.CharField(max_length=128, blank=True, default='')
    realm = models.CharField(max_length=256, blank=True, default='')
    from_user = models.CharField(max_length=128, blank=True, default='')
    from_domain = models.CharField(max_length=256, blank=True, default='')
    proxy = models.CharField(max_length=256, blank=True, default='')
    register_proxy = models.CharField(max_length=256, blank=True, default='')
    outbound_proxy = models.CharField(max_length=256, blank=True, default='')
    expire_seconds = models.IntegerField(default=3600)
    register = models.BooleanField(default=True)
    register_transport = models.CharField(max_length=8, default='udp',
        choices=[('udp','UDP'),('tcp','TCP'),('tls','TLS')])
    retry_seconds = models.IntegerField(default=30)
    extension = models.CharField(max_length=32, default='auto_to_user')
    ping = models.CharField(max_length=64, blank=True, default='')
    ping_max = models.IntegerField(default=3)
    ping_min = models.IntegerField(default=1)
    caller_id_in_from = models.BooleanField(default=False)
    codec_prefs = models.CharField(max_length=128, default='PCMU,PCMA')
    inbound_codec_prefs = models.CharField(max_length=128, default='PCMU,PCMA')
    outbound_codec_prefs = models.CharField(max_length=128, default='PCMU,PCMA')
    profile = models.CharField(max_length=64, default='external')
    gateway_enabled = models.BooleanField(default=True)
    gateway_description = models.TextField(blank=True, default='')
    insert_date = models.DateTimeField(auto_now_add=True, null=True)
    insert_user = models.UUIDField(null=True, blank=True)
    update_date = models.DateTimeField(auto_now=True, null=True)
    update_user = models.UUIDField(null=True, blank=True)

    class Meta:
        db_table = 'v_gateways'

    def __str__(self):
        return self.gateway
