import uuid
from django.db import models
from core.models import Domain

class EventGuard(models.Model):
    event_guard_uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        'core.Tenant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column='tenant_uuid',
        related_name='%(app_label)s_%(class)s_set',
    )
    domain = models.ForeignKey(Domain, on_delete=models.CASCADE, null=True, blank=True, db_column='domain_uuid')
    event_guard_name = models.CharField(max_length=255)
    event_guard_type = models.CharField(max_length=64, blank=True)
    event_guard_expression = models.CharField(max_length=512, blank=True)
    event_guard_action = models.CharField(max_length=64, blank=True)
    event_guard_count = models.IntegerField(default=1)
    event_guard_period = models.IntegerField(default=60)
    event_guard_enabled = models.BooleanField(default=True)
    event_guard_description = models.TextField(blank=True)
    insert_date = models.DateTimeField(auto_now_add=True)
    insert_user = models.UUIDField(null=True, blank=True)
    update_date = models.DateTimeField(auto_now=True)
    update_user = models.UUIDField(null=True, blank=True)

    class Meta:
        db_table = 'v_event_guard'

    def __str__(self):
        return self.event_guard_name
