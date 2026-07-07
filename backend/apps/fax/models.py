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
    # How received faxes are delivered: emailed, uploaded to an FTP server, or both.
    FAX_DELIVERY_MODES = [('email', 'Email'), ('ftp', 'FTP'), ('both', 'Email + FTP')]
    fax_delivery_mode = models.CharField(max_length=10, choices=FAX_DELIVERY_MODES, default='email')
    # FTP/FTPS store-and-forward target for inbound faxes.
    fax_ftp_host = models.CharField(max_length=255, blank=True)
    fax_ftp_port = models.IntegerField(default=21)
    fax_ftp_username = models.CharField(max_length=255, blank=True)
    fax_ftp_password = models.CharField(max_length=255, blank=True)
    fax_ftp_path = models.CharField(max_length=512, blank=True)
    fax_ftp_use_tls = models.BooleanField(default=False)
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


class FaxFtpDelivery(models.Model):
    """Audit log of inbound-fax FTP/FTPS upload attempts.

    Mirrors WebhookDelivery (apps.client_api): one row per fax file delivery,
    updated in place across retry attempts so the admin shows current status,
    attempt count, last error and the remote target.
    """
    STATUS_PENDING = 'pending'
    STATUS_SUCCESS = 'success'
    STATUS_FAILED = 'failed'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_SUCCESS, 'Success'),
        (STATUS_FAILED, 'Failed'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    fax = models.ForeignKey(Fax, on_delete=models.CASCADE, related_name='ftp_deliveries',
                            null=True, blank=True, db_column='fax_uuid')
    fax_file = models.ForeignKey(FaxFile, on_delete=models.CASCADE, related_name='ftp_deliveries',
                                 null=True, blank=True, db_column='fax_file_uuid')
    tenant = models.ForeignKey(
        'core.Tenant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column='tenant_uuid',
        related_name='%(app_label)s_%(class)s_set',
    )
    # Snapshot of the target at attempt time (config can change later).
    host = models.CharField(max_length=255, blank=True, default='')
    port = models.IntegerField(default=21)
    username = models.CharField(max_length=255, blank=True, default='')
    remote_path = models.CharField(max_length=512, blank=True, default='')
    remote_name = models.CharField(max_length=512, blank=True, default='')
    use_tls = models.BooleanField(default=False)
    file_size_bytes = models.IntegerField(null=True, blank=True)

    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_PENDING)
    attempts = models.PositiveSmallIntegerField(default=0)
    last_response = models.TextField(blank=True, default='')
    last_error = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    delivered_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'v_fax_ftp_deliveries'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['fax', 'status']),
            models.Index(fields=['status', 'created_at']),
        ]

    def __str__(self):
        return f'{self.remote_name} -> {self.host} ({self.status})'
