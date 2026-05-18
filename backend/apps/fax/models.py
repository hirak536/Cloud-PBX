import uuid
from django.db import models
from core.models import Domain

class Fax(models.Model):
    fax_uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        'core.Tenant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column='tenant_uuid',
        related_name='%(app_label)s_%(class)s_set',
    )
    domain = models.ForeignKey(Domain, on_delete=models.CASCADE, null=True, blank=True, db_column='domain_uuid')
    fax_name = models.CharField(max_length=255)
    fax_extension = models.CharField(max_length=255, blank=True)
    fax_email = models.CharField(max_length=255, blank=True)
    fax_email_connection = models.CharField(max_length=255, blank=True)
    fax_caller_id_name = models.CharField(max_length=255, blank=True)
    fax_caller_id_number = models.CharField(max_length=255, blank=True)
    fax_forward_number = models.CharField(max_length=255, blank=True)
    fax_toll_allow = models.CharField(max_length=255, blank=True)
    fax_accountcode = models.CharField(max_length=255, blank=True)
    fax_enabled = models.BooleanField(default=True)
    fax_description = models.TextField(blank=True)
    insert_date = models.DateTimeField(auto_now_add=True)
    insert_user = models.UUIDField(null=True, blank=True)
    update_date = models.DateTimeField(auto_now=True)
    update_user = models.UUIDField(null=True, blank=True)

    class Meta:
        db_table = 'v_fax'

    def __str__(self):
        return self.fax_name

class FaxFile(models.Model):
    FAX_STATUSES = [('sent', 'Sent'), ('received', 'Received'), ('pending', 'Pending'), ('failed', 'Failed')]
    FAX_DIRECTIONS = [('inbound', 'Inbound'), ('outbound', 'Outbound')]

    fax_file_uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    fax = models.ForeignKey(Fax, on_delete=models.CASCADE, related_name='files', db_column='fax_uuid', null=True, blank=True)
    tenant = models.ForeignKey(
        'core.Tenant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column='tenant_uuid',
        related_name='%(app_label)s_%(class)s_set',
    )
    domain = models.ForeignKey(Domain, on_delete=models.CASCADE, null=True, blank=True, db_column='domain_uuid')
    fax_file_type = models.CharField(max_length=10, default='pdf')
    fax_file_name = models.CharField(max_length=512)
    fax_file_path = models.CharField(max_length=512, blank=True)
    direction = models.CharField(max_length=10, choices=FAX_DIRECTIONS, default='outbound')
    fax_file_status = models.CharField(max_length=20, choices=FAX_STATUSES, default='pending')
    fax_file_pages = models.IntegerField(default=0)
    fax_file_duration = models.IntegerField(default=0)
    fax_file_caller_id_name = models.CharField(max_length=255, blank=True)
    fax_file_caller_id_number = models.CharField(max_length=255, blank=True)
    fax_file_destination_number = models.CharField(max_length=255, blank=True)
    fax_file_station_id = models.CharField(max_length=255, blank=True)
    fax_file_date = models.DateTimeField(null=True, blank=True)
    channel_uuid = models.CharField(max_length=64, blank=True, db_index=True)
    retry_count = models.IntegerField(default=0)
    insert_date = models.DateTimeField(auto_now_add=True)

    @property
    def file_size_bytes(self):
        import os
        path = self.fax_file_path
        if path and os.path.isfile(path):
            return os.path.getsize(path)
        return None

    class Meta:
        db_table = 'v_fax_files'
        ordering = ['-insert_date']
