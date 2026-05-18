import uuid
from django.db import models


class SofiaGlobalSetting(models.Model):
    sofia_global_setting_uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sofia_global_setting_name = models.CharField(max_length=128)
    sofia_global_setting_value = models.TextField(blank=True, default='')
    sofia_global_setting_enabled = models.BooleanField(default=True)
    sofia_global_setting_description = models.TextField(blank=True, default='')
    insert_date = models.DateTimeField(auto_now_add=True, null=True)
    insert_user = models.UUIDField(null=True, blank=True)
    update_date = models.DateTimeField(auto_now=True, null=True)
    update_user = models.UUIDField(null=True, blank=True)

    class Meta:
        db_table = 'v_sofia_global_settings'
        ordering = ['sofia_global_setting_name']

    def __str__(self):
        return f'{self.sofia_global_setting_name} = {self.sofia_global_setting_value}'
