import uuid
from django.db import models
from core.models import Domain

class CallFlow(models.Model):
    call_flow_uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        'core.Tenant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column='tenant_uuid',
        related_name='%(app_label)s_%(class)s_set',
    )
    domain = models.ForeignKey(Domain, on_delete=models.CASCADE, null=True, blank=True, db_column='domain_uuid')
    call_flow_name = models.CharField(max_length=255)
    call_flow_extension = models.CharField(max_length=255, blank=True)
    call_flow_feature_code = models.CharField(max_length=50, blank=True)
    call_flow_status = models.CharField(max_length=10, default='true')
    call_flow_sound = models.CharField(max_length=255, blank=True)
    call_flow_greeting = models.CharField(max_length=255, blank=True)
    call_flow_context = models.CharField(max_length=128, blank=True)
    call_flow_enabled = models.BooleanField(default=True)
    call_flow_description = models.TextField(blank=True)

    # Day (open) destination
    day_dest_type = models.CharField(max_length=64, blank=True)
    day_dest_target_uuid = models.UUIDField(null=True, blank=True)
    day_dest_external_number = models.CharField(max_length=64, blank=True)

    # Night (closed) destination
    night_dest_type = models.CharField(max_length=64, blank=True)
    night_dest_target_uuid = models.UUIDField(null=True, blank=True)
    night_dest_external_number = models.CharField(max_length=64, blank=True)
    insert_date = models.DateTimeField(auto_now_add=True)
    insert_user = models.UUIDField(null=True, blank=True)
    update_date = models.DateTimeField(auto_now=True)
    update_user = models.UUIDField(null=True, blank=True)

    class Meta:
        db_table = 'v_call_flows'

    def __str__(self):
        return self.call_flow_name

class CallFlowOption(models.Model):
    call_flow_option_uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    call_flow = models.ForeignKey(CallFlow, on_delete=models.CASCADE, related_name='options', db_column='call_flow_uuid')
    tenant = models.ForeignKey(
        'core.Tenant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column='tenant_uuid',
        related_name='%(app_label)s_%(class)s_set',
    )
    domain = models.ForeignKey(Domain, on_delete=models.CASCADE, null=True, blank=True, db_column='domain_uuid')
    call_flow_option_order = models.IntegerField(default=0)
    call_flow_option_enabled = models.BooleanField(default=True)
    call_flow_option_destination = models.CharField(max_length=255, blank=True)
    call_flow_option_app = models.CharField(max_length=128, blank=True)
    call_flow_option_param = models.CharField(max_length=255, blank=True)
    insert_date = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'v_call_flow_options'
        ordering = ['call_flow_option_order']
