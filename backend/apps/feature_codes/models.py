import uuid
from django.db import models
from core.models import Domain

class FeatureCode(models.Model):
    feature_code_uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        'core.Tenant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column='tenant_uuid',
        related_name='%(app_label)s_%(class)s_set',
    )
    domain = models.ForeignKey(Domain, on_delete=models.CASCADE, null=True, blank=True, db_column='domain_uuid')
    dialplan_uuid = models.UUIDField(null=True, blank=True)
    feature_code_name = models.CharField(max_length=255)
    feature_code_description = models.TextField(blank=True)
    # Stable slug the dialplan generator looks the code up by (e.g.
    # 'on_demand_recording'). The name is a human label and may be renamed;
    # the key must not be, since generators.py keys off it.
    feature_code_key = models.CharField(max_length=64, blank=True, default='')
    # The digits the user actually dials/presses (e.g. '*2').
    feature_code_number = models.CharField(max_length=32, blank=True, default='')
    feature_code_enabled = models.BooleanField(default=True)
    insert_date = models.DateTimeField(auto_now_add=True)
    insert_user = models.UUIDField(null=True, blank=True)
    update_date = models.DateTimeField(auto_now=True)
    update_user = models.UUIDField(null=True, blank=True)

    class Meta:
        db_table = 'v_feature_codes'

    def __str__(self):
        return self.feature_code_name
