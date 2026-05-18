import uuid
from django.db import models


class ProvisionTemplate(models.Model):
    """Stores phone provisioning templates per vendor/model.

    Templates use Django template syntax. The context provided during
    rendering includes:
      - ``device``:   the Device instance
      - ``domain``:   device.domain
      - ``lines``:    enabled DeviceLine queryset ordered by line_number
      - ``settings``: dict of {device_setting_name: device_setting_value}
    """

    template_uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    vendor = models.CharField(max_length=64)
    model = models.CharField(max_length=64, blank=True, default='')
    firmware_version = models.CharField(max_length=32, blank=True, default='')
    template_name = models.CharField(max_length=128)
    template_content = models.TextField()
    content_type = models.CharField(max_length=32, default='text/xml')
    is_active = models.BooleanField(default=True)
    insert_date = models.DateTimeField(auto_now_add=True)
    update_date = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'v_provision_templates'
        unique_together = [('vendor', 'model', 'firmware_version', 'template_name')]

    def __str__(self):
        parts = [self.vendor]
        if self.model:
            parts.append(self.model)
        if self.firmware_version:
            parts.append(self.firmware_version)
        parts.append(self.template_name)
        return ' / '.join(parts)
