import uuid
from django.db import models
from core.models import Domain

class Fifo(models.Model):
    fifo_uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        'core.Tenant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column='tenant_uuid',
        related_name='%(app_label)s_%(class)s_set',
    )
    domain = models.ForeignKey(Domain, on_delete=models.CASCADE, null=True, blank=True, db_column='domain_uuid')
    fifo_name = models.CharField(max_length=255)
    fifo_label = models.CharField(max_length=255, blank=True)
    fifo_extension = models.CharField(max_length=255, blank=True)
    fifo_announcement = models.CharField(max_length=255, blank=True)
    fifo_music = models.CharField(max_length=255, blank=True)
    fifo_strategy = models.CharField(max_length=64, default='default')
    fifo_caller_hang_up_opt = models.CharField(max_length=10, blank=True)
    fifo_caller_exit_key = models.CharField(max_length=10, blank=True)
    fifo_max_wait_time = models.IntegerField(default=0)
    fifo_max_wait_time_with_no_agent = models.IntegerField(default=0)
    fifo_timeout_priority = models.CharField(max_length=10, blank=True)
    fifo_pop_on_lost_agent = models.CharField(max_length=10, default='true')
    fifo_enabled = models.BooleanField(default=True)
    fifo_description = models.TextField(blank=True)
    insert_date = models.DateTimeField(auto_now_add=True)
    insert_user = models.UUIDField(null=True, blank=True)
    update_date = models.DateTimeField(auto_now=True)
    update_user = models.UUIDField(null=True, blank=True)

    class Meta:
        db_table = 'v_fifo'

    def __str__(self):
        return self.fifo_name

class FifoCallers(models.Model):
    fifo_caller_uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    fifo = models.ForeignKey(Fifo, on_delete=models.CASCADE, related_name='callers', db_column='fifo_uuid')
    tenant = models.ForeignKey(
        'core.Tenant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column='tenant_uuid',
        related_name='%(app_label)s_%(class)s_set',
    )
    domain = models.ForeignKey(Domain, on_delete=models.CASCADE, null=True, blank=True, db_column='domain_uuid')
    fifo_caller_caller_id_name = models.CharField(max_length=255, blank=True)
    fifo_caller_caller_id_number = models.CharField(max_length=255, blank=True)
    fifo_caller_status = models.CharField(max_length=20, default='waiting')
    insert_date = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'v_fifo_callers'
