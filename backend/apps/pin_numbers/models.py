import uuid
from django.db import models
from core.models import Domain

class PinNumber(models.Model):
    pin_number_uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        'core.Tenant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column='tenant_uuid',
        related_name='%(app_label)s_%(class)s_set',
    )
    domain = models.ForeignKey(Domain, on_delete=models.CASCADE, null=True, blank=True, db_column='domain_uuid')
    pin_number = models.CharField(max_length=64)
    pin_number_limit = models.CharField(max_length=64, blank=True)
    pin_number_toll_allow = models.CharField(max_length=255, blank=True)
    pin_number_accountcode = models.CharField(max_length=255, blank=True)
    pin_number_enabled = models.BooleanField(default=True)
    pin_number_description = models.TextField(blank=True)
    insert_date = models.DateTimeField(auto_now_add=True)
    insert_user = models.UUIDField(null=True, blank=True)
    update_date = models.DateTimeField(auto_now=True)
    update_user = models.UUIDField(null=True, blank=True)

    class Meta:
        db_table = 'v_pin_numbers'

    def __str__(self):
        return self.pin_number
