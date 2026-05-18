import uuid
from django.db import models
from core.models import Domain

class ExtensionSetting(models.Model):
    extension_setting_uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        'core.Tenant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column='tenant_uuid',
        related_name='%(app_label)s_%(class)s_set',
    )
    domain = models.ForeignKey(Domain, on_delete=models.CASCADE, null=True, blank=True, db_column='domain_uuid')
    extension_uuid = models.UUIDField()
    extension_setting_category = models.CharField(max_length=255, blank=True)
    extension_setting_subcategory = models.CharField(max_length=255, blank=True)
    extension_setting_name = models.CharField(max_length=255)
    extension_setting_value = models.TextField(blank=True)
    extension_setting_order = models.IntegerField(default=0)
    extension_setting_enabled = models.BooleanField(default=True)
    extension_setting_description = models.TextField(blank=True)
    insert_date = models.DateTimeField(auto_now_add=True)
    insert_user = models.UUIDField(null=True, blank=True)
    update_date = models.DateTimeField(auto_now=True)
    update_user = models.UUIDField(null=True, blank=True)

    class Meta:
        db_table = 'v_extension_settings'
        ordering = ['extension_setting_order']

    def __str__(self):
        return f'{self.extension_setting_name}={self.extension_setting_value}'
