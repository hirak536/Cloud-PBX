import uuid
from django.db import models
from core.models import Domain

class Device(models.Model):
    device_uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        'core.Tenant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column='tenant_uuid',
        related_name='%(app_label)s_%(class)s_set',
    )
    domain = models.ForeignKey(Domain, on_delete=models.CASCADE, null=True, blank=True, db_column='domain_uuid')
    device_label = models.CharField(max_length=255, blank=True)
    device_mac_address = models.CharField(max_length=255, blank=True)
    device_vendor = models.CharField(max_length=255, blank=True)
    device_model = models.CharField(max_length=255, blank=True)
    device_firmware_version = models.CharField(max_length=255, blank=True)
    device_profile_uuid = models.UUIDField(null=True, blank=True)
    device_enabled = models.BooleanField(default=True)
    device_enabled_date = models.DateTimeField(null=True, blank=True)
    device_description = models.TextField(blank=True)
    insert_date = models.DateTimeField(auto_now_add=True)
    insert_user = models.UUIDField(null=True, blank=True)
    update_date = models.DateTimeField(auto_now=True)
    update_user = models.UUIDField(null=True, blank=True)

    class Meta:
        db_table = 'v_devices'

    def __str__(self):
        return f'{self.device_mac_address} ({self.device_vendor})'

class DeviceLine(models.Model):
    device_line_uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name='lines', db_column='device_uuid')
    tenant = models.ForeignKey(
        'core.Tenant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column='tenant_uuid',
        related_name='%(app_label)s_%(class)s_set',
    )
    domain = models.ForeignKey(Domain, on_delete=models.CASCADE, null=True, blank=True, db_column='domain_uuid')
    line_number = models.IntegerField(default=1)
    device_line_server_address = models.CharField(max_length=255, blank=True)
    device_line_label = models.CharField(max_length=255, blank=True)
    device_line_username = models.CharField(max_length=255, blank=True)
    device_line_password = models.CharField(max_length=255, blank=True)
    device_line_auth_id = models.CharField(max_length=255, blank=True)
    device_line_extension = models.CharField(max_length=255, blank=True)
    device_line_display_name = models.CharField(max_length=255, blank=True)
    device_line_enabled = models.BooleanField(default=True)
    insert_date = models.DateTimeField(auto_now_add=True)
    insert_user = models.UUIDField(null=True, blank=True)

    class Meta:
        db_table = 'v_device_lines'
        ordering = ['line_number']

class DeviceSetting(models.Model):
    device_setting_uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name='settings', db_column='device_uuid')
    tenant = models.ForeignKey(
        'core.Tenant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column='tenant_uuid',
        related_name='%(app_label)s_%(class)s_set',
    )
    domain = models.ForeignKey(Domain, on_delete=models.CASCADE, null=True, blank=True, db_column='domain_uuid')
    device_setting_name = models.CharField(max_length=255)
    device_setting_value = models.TextField(blank=True)
    device_setting_enabled = models.BooleanField(default=True)
    device_setting_description = models.TextField(blank=True)

    class Meta:
        db_table = 'v_device_settings'
