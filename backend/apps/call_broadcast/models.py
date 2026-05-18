import uuid
from django.db import models
from core.models import Domain

class CallBroadcast(models.Model):
    call_broadcast_uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        'core.Tenant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column='tenant_uuid',
        related_name='%(app_label)s_%(class)s_set',
    )
    domain = models.ForeignKey(Domain, on_delete=models.CASCADE, null=True, blank=True, db_column='domain_uuid')
    call_broadcast_name = models.CharField(max_length=255)
    call_broadcast_caller_id_name = models.CharField(max_length=255, blank=True)
    call_broadcast_caller_id_number = models.CharField(max_length=255, blank=True)
    call_broadcast_timeout = models.IntegerField(default=60)
    call_broadcast_context = models.CharField(max_length=128, blank=True)
    call_broadcast_recording = models.CharField(max_length=512, blank=True)
    call_broadcast_enabled = models.BooleanField(default=True)
    call_broadcast_description = models.TextField(blank=True)
    insert_date = models.DateTimeField(auto_now_add=True)
    insert_user = models.UUIDField(null=True, blank=True)
    update_date = models.DateTimeField(auto_now=True)
    update_user = models.UUIDField(null=True, blank=True)

    class Meta:
        db_table = 'v_call_broadcast'

    def __str__(self):
        return self.call_broadcast_name

class CallBroadcastContact(models.Model):
    call_broadcast_contact_uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    call_broadcast = models.ForeignKey(CallBroadcast, on_delete=models.CASCADE, related_name='contacts', db_column='call_broadcast_uuid')
    tenant = models.ForeignKey(
        'core.Tenant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column='tenant_uuid',
        related_name='%(app_label)s_%(class)s_set',
    )
    domain = models.ForeignKey(Domain, on_delete=models.CASCADE, null=True, blank=True, db_column='domain_uuid')
    call_broadcast_contact_number = models.CharField(max_length=255)
    call_broadcast_contact_status = models.CharField(max_length=20, default='pending')
    insert_date = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'v_call_broadcast_contacts'
