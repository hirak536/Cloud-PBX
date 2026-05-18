import uuid
from django.db import models
from core.models import Domain

class Emergency(models.Model):
    emergency_uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        'core.Tenant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column='tenant_uuid',
        related_name='%(app_label)s_%(class)s_set',
    )
    domain = models.ForeignKey(Domain, on_delete=models.CASCADE, null=True, blank=True, db_column='domain_uuid')
    emergency_number = models.CharField(max_length=64)
    emergency_destination = models.CharField(max_length=255, blank=True)
    emergency_context = models.CharField(max_length=128, blank=True)
    emergency_enabled = models.BooleanField(default=True)
    emergency_description = models.TextField(blank=True)
    insert_date = models.DateTimeField(auto_now_add=True)
    insert_user = models.UUIDField(null=True, blank=True)
    update_date = models.DateTimeField(auto_now=True)
    update_user = models.UUIDField(null=True, blank=True)

    class Meta:
        db_table = 'v_emergency'

    def __str__(self):
        return self.emergency_number
