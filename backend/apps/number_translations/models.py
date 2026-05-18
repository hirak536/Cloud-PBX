import uuid
from django.db import models
from core.models import Domain

class NumberTranslation(models.Model):
    number_translation_uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        'core.Tenant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column='tenant_uuid',
        related_name='%(app_label)s_%(class)s_set',
    )
    domain = models.ForeignKey(Domain, on_delete=models.CASCADE, null=True, blank=True, db_column='domain_uuid')
    number_translation_name = models.CharField(max_length=255)
    number_translation_description = models.TextField(blank=True)
    insert_date = models.DateTimeField(auto_now_add=True)
    insert_user = models.UUIDField(null=True, blank=True)
    update_date = models.DateTimeField(auto_now=True)
    update_user = models.UUIDField(null=True, blank=True)

    class Meta:
        db_table = 'v_number_translations'

    def __str__(self):
        return self.number_translation_name

class NumberTranslationDetail(models.Model):
    number_translation_detail_uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    number_translation = models.ForeignKey(NumberTranslation, on_delete=models.CASCADE, related_name='details', db_column='number_translation_uuid')
    tenant = models.ForeignKey(
        'core.Tenant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column='tenant_uuid',
        related_name='%(app_label)s_%(class)s_set',
    )
    domain = models.ForeignKey(Domain, on_delete=models.CASCADE, null=True, blank=True, db_column='domain_uuid')
    number_translation_detail_order = models.IntegerField(default=10)
    number_translation_detail_condition_field = models.CharField(max_length=64, blank=True)
    number_translation_detail_condition_expression = models.CharField(max_length=255, blank=True)
    number_translation_detail_action_expression = models.CharField(max_length=255, blank=True)
    insert_date = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'v_number_translation_details'
        ordering = ['number_translation_detail_order']
