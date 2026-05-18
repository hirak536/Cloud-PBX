import uuid
from django.db import models
from core.models import Domain

class CallBlock(models.Model):
    ACTIONS = [('block', 'Block'), ('allow', 'Allow')]

    call_block_uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        'core.Tenant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column='tenant_uuid',
        related_name='%(app_label)s_%(class)s_set',
    )
    domain = models.ForeignKey(Domain, on_delete=models.CASCADE, null=True, blank=True, db_column='domain_uuid')
    call_block_number = models.CharField(max_length=255)
    call_block_action = models.CharField(max_length=10, choices=ACTIONS, default='block')
    call_block_enabled = models.BooleanField(default=True)
    call_block_description = models.TextField(blank=True)
    insert_date = models.DateTimeField(auto_now_add=True)
    insert_user = models.UUIDField(null=True, blank=True)
    update_date = models.DateTimeField(auto_now=True)
    update_user = models.UUIDField(null=True, blank=True)

    class Meta:
        db_table = 'v_call_block'

    def __str__(self):
        return f'{self.call_block_number} ({self.call_block_action})'
