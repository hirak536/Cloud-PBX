import uuid
from django.db import models
from core.models import Domain


class OutboundRoute(models.Model):
    outbound_route_uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
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
        related_name='outbound_routes',
    )
    outbound_route_name = models.CharField(max_length=64, help_text='Human-readable label (e.g. Local Calls)')
    outbound_route_order = models.IntegerField(
        default=10,
        help_text='Priority — lower numbers are matched first.',
    )
    # Pattern that FreeSWITCH tests against destination_number.
    # Should capture the digits-to-dial in group 1, e.g. ^9(\d{10})$
    dialplan_pattern = models.CharField(
        max_length=128,
        help_text='Regex matched against the dialed number. Use a capture group for the part to send, e.g. ^9(\\d{10})$',
    )
    # Digits prepended to the captured group before dialling the gateway.
    prepend = models.CharField(
        max_length=32,
        blank=True,
        default='',
        help_text='Digits to prepend before the captured number when bridging, e.g. "1".',
    )
    # Primary gateway (required)
    gateway = models.ForeignKey(
        'gateways.Gateway',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column='gateway_uuid',
        related_name='outbound_routes',
        verbose_name='Gateway',
    )
    # Optional failover gateways
    gateway_2 = models.ForeignKey(
        'gateways.Gateway',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column='gateway_2_uuid',
        related_name='outbound_routes_failover_1',
        verbose_name='Failover gateway',
    )
    gateway_3 = models.ForeignKey(
        'gateways.Gateway',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column='gateway_3_uuid',
        related_name='outbound_routes_failover_2',
        verbose_name='2nd failover gateway',
    )
    caller_id_number = models.CharField(
        max_length=32,
        blank=True,
        default='',
        help_text='Verified caller ID number to present to the carrier (e.g. 12818545006). Overrides the channel caller ID.',
    )
    caller_id_name = models.CharField(
        max_length=32,
        blank=True,
        default='',
        help_text='Caller ID name to present to the carrier. Defaults to caller_id_number if blank.',
    )
    outbound_route_enabled = models.BooleanField(default=True)
    outbound_route_description = models.TextField(blank=True, default='')
    insert_date = models.DateTimeField(auto_now_add=True, null=True)
    insert_user = models.UUIDField(null=True, blank=True)
    update_date = models.DateTimeField(auto_now=True, null=True)
    update_user = models.UUIDField(null=True, blank=True)

    class Meta:
        db_table = 'v_outbound_routes'
        ordering = ['outbound_route_order', 'outbound_route_name']

    def __str__(self):
        return self.outbound_route_name
