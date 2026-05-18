import uuid
from django.db import models
from core.models import Domain


class RingGroup(models.Model):
    STRATEGY_CHOICES = [
        ('simultaneous','Simultaneous'),('sequence','Sequence'),
        ('enterprise','Enterprise'),('rollover','Rollover'),
    ]
    ring_group_uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        'core.Tenant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column='tenant_uuid',
        related_name='%(app_label)s_%(class)s_set',
    )
    domain = models.ForeignKey(Domain, on_delete=models.CASCADE, db_column='domain_uuid', related_name='ring_groups')
    ring_group_name = models.CharField(max_length=128)
    ring_group_extension = models.CharField(max_length=32, blank=True, default='')
    ring_group_greeting = models.CharField(max_length=256, blank=True, default='')
    ring_group_cid_name_prefix = models.CharField(max_length=64, blank=True, default='')
    ring_group_cid_number_prefix = models.CharField(max_length=16, blank=True, default='')
    ring_group_caller_id_name = models.CharField(max_length=128, blank=True, default='')
    ring_group_caller_id_number = models.CharField(max_length=32, blank=True, default='')
    ring_group_strategy = models.CharField(max_length=32, choices=STRATEGY_CHOICES, default='simultaneous')
    ring_group_call_timeout = models.IntegerField(default=60)
    ring_group_dial_timeout = models.IntegerField(default=3600)
    ring_group_timeout_app = models.CharField(max_length=64, blank=True, default='')
    ring_group_timeout_data = models.CharField(max_length=256, blank=True, default='')
    ring_group_timeout_type = models.CharField(max_length=32, blank=True, default='')
    ring_group_timeout_target_uuid = models.UUIDField(null=True, blank=True)
    ring_group_timeout_external_number = models.CharField(max_length=64, blank=True, default='')
    ring_group_ringback = models.CharField(max_length=256, blank=True, default='')
    ring_group_context = models.CharField(max_length=128, default='default')
    ring_group_enabled = models.BooleanField(default=True)
    ring_group_description = models.TextField(blank=True, default='')
    ring_group_skip_busy = models.BooleanField(default=False)
    ring_group_skip_offline = models.BooleanField(default=False)
    ring_group_fast_dial = models.BooleanField(default=False)
    ring_group_moh_sound = models.BooleanField(default=False)
    ring_group_allow_redirect = models.BooleanField(default=False)
    ring_group_allow_fmfm = models.BooleanField(default=False)
    ring_group_allow_additional_destinations = models.BooleanField(default=False)
    ring_group_use_custom_destination = models.BooleanField(default=False)
    ring_group_confirm_to_answer = models.BooleanField(default=False)
    ring_group_confirm_message = models.CharField(max_length=256, blank=True, default='')
    ring_group_use_standard_message = models.BooleanField(default=True)
    insert_date = models.DateTimeField(auto_now_add=True, null=True)
    insert_user = models.UUIDField(null=True, blank=True)
    update_date = models.DateTimeField(auto_now=True, null=True)
    update_user = models.UUIDField(null=True, blank=True)

    class Meta:
        db_table = 'v_ring_groups'
        unique_together = [('tenant', 'ring_group_extension')]

    def __str__(self):
        return f'{self.ring_group_name} ({self.ring_group_extension})'

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)


class RingGroupDestination(models.Model):
    ring_group_destination_uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        'core.Tenant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column='tenant_uuid',
        related_name='%(app_label)s_%(class)s_set',
    )
    domain = models.ForeignKey(Domain, on_delete=models.CASCADE, null=True, db_column='domain_uuid')
    ring_group = models.ForeignKey(RingGroup, on_delete=models.CASCADE,
                                   db_column='ring_group_uuid', related_name='destinations')
    destination_number = models.CharField(max_length=64)
    destination_delay = models.IntegerField(default=0)
    destination_timeout = models.IntegerField(default=30)
    destination_prompt = models.CharField(max_length=256, blank=True, default='')
    insert_date = models.DateTimeField(auto_now_add=True, null=True)

    class Meta:
        db_table = 'v_ring_group_destinations'
        ordering = ['destination_delay', 'destination_number']
