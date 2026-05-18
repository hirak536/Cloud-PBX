import uuid
from django.db import models
from core.models import Domain

class Recording(models.Model):
    recording_uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        'core.Tenant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column='tenant_uuid',
        related_name='%(app_label)s_%(class)s_set',
    )
    domain = models.ForeignKey(Domain, on_delete=models.CASCADE, null=True, blank=True, db_column='domain_uuid')
    recording_name = models.CharField(max_length=255)
    recording_filename = models.CharField(max_length=255)
    recording_description = models.TextField(blank=True)
    recording_base64 = models.TextField(blank=True)
    recording_volume = models.FloatField(default=1.0)
    recording_format = models.CharField(max_length=32, blank=True, default='auto')
    insert_date = models.DateTimeField(auto_now_add=True)
    insert_user = models.UUIDField(null=True, blank=True)
    update_date = models.DateTimeField(auto_now=True)
    update_user = models.UUIDField(null=True, blank=True)

    class Meta:
        db_table = 'v_recordings'

    def __str__(self):
        return self.recording_name

class CallRecording(models.Model):
    call_recording_uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        'core.Tenant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column='tenant_uuid',
        related_name='%(app_label)s_%(class)s_set',
    )
    domain = models.ForeignKey(Domain, on_delete=models.CASCADE, null=True, blank=True, db_column='domain_uuid')
    call_recording_filename = models.CharField(max_length=512)
    call_recording_caller_id_name = models.CharField(max_length=255, blank=True)
    call_recording_caller_id_number = models.CharField(max_length=255, blank=True)
    call_recording_destination_number = models.CharField(max_length=255, blank=True)
    call_recording_start_stamp = models.DateTimeField(null=True, blank=True)
    call_recording_duration = models.IntegerField(default=0)
    call_recording_billsec = models.IntegerField(default=0)
    insert_date = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'v_call_recordings'
        ordering = ['-insert_date']
