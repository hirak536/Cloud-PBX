import uuid
from django.db import models
from core.models import Domain

class TimeCondition(models.Model):
    dialplan_uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        'core.Tenant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column='tenant_uuid',
        related_name='%(app_label)s_%(class)s_set',
    )
    domain = models.ForeignKey(Domain, on_delete=models.CASCADE, null=True, blank=True, db_column='domain_uuid')
    dialplan_name = models.CharField(max_length=255)
    dialplan_extension = models.CharField(max_length=255, blank=True)
    dialplan_context = models.CharField(max_length=128, blank=True)
    dialplan_enabled = models.BooleanField(default=True)
    dialplan_description = models.TextField(blank=True)
    insert_date = models.DateTimeField(auto_now_add=True)
    insert_user = models.UUIDField(null=True, blank=True)
    update_date = models.DateTimeField(auto_now=True)
    update_user = models.UUIDField(null=True, blank=True)

    class Meta:
        db_table = 'v_time_conditions'

    def __str__(self):
        return self.dialplan_name

class TimeConditionRange(models.Model):
    time_condition_uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    dialplan = models.ForeignKey(TimeCondition, on_delete=models.CASCADE, related_name='ranges', db_column='dialplan_uuid')
    tenant = models.ForeignKey(
        'core.Tenant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column='tenant_uuid',
        related_name='%(app_label)s_%(class)s_set',
    )
    domain = models.ForeignKey(Domain, on_delete=models.CASCADE, null=True, blank=True, db_column='domain_uuid')
    time_condition_order = models.IntegerField(default=900)
    time_condition_enabled = models.BooleanField(default=True)
    # Time range criteria
    time_condition_year = models.CharField(max_length=64, blank=True)
    time_condition_yday = models.CharField(max_length=64, blank=True)
    time_condition_mon = models.CharField(max_length=64, blank=True)
    time_condition_mday = models.CharField(max_length=64, blank=True)
    time_condition_week = models.CharField(max_length=64, blank=True)
    time_condition_mweek = models.CharField(max_length=64, blank=True)
    time_condition_wday = models.CharField(max_length=64, blank=True)
    time_condition_hour = models.CharField(max_length=64, blank=True)
    time_condition_minute = models.CharField(max_length=64, blank=True)
    time_condition_minute_of_day = models.CharField(max_length=64, blank=True)
    time_condition_time_of_day = models.CharField(max_length=64, blank=True)
    time_condition_date_time = models.CharField(max_length=64, blank=True)
    # Destinations
    time_condition_destination_number = models.CharField(max_length=255, blank=True)
    time_condition_destination_action = models.CharField(max_length=64, blank=True)
    time_condition_destination_app = models.CharField(max_length=128, blank=True)
    time_condition_destination_param = models.CharField(max_length=255, blank=True)
    insert_date = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'v_time_condition_ranges'
        ordering = ['time_condition_order']
