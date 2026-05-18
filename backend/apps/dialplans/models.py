import uuid
from django.db import models
from core.models import Domain


class Dialplan(models.Model):
    dialplan_uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        'core.Tenant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column='tenant_uuid',
        related_name='%(app_label)s_%(class)s_set',
    )
    domain = models.ForeignKey(Domain, on_delete=models.CASCADE, null=True, blank=True,
                               db_column='domain_uuid', related_name='dialplans')
    app_uuid = models.UUIDField(null=True, blank=True)
    dialplan_context = models.CharField(max_length=128, default='default')
    dialplan_name = models.CharField(max_length=128, blank=True, default='')
    dialplan_number = models.CharField(max_length=32, blank=True, default='')
    dialplan_destination = models.BooleanField(default=False)
    dialplan_continue = models.CharField(max_length=8, blank=True, default='')
    dialplan_xml = models.TextField(blank=True, default='')
    dialplan_order = models.IntegerField(default=100)
    dialplan_enabled = models.BooleanField(default=True)
    dialplan_global = models.BooleanField(default=False)
    dialplan_description = models.TextField(blank=True, default='')
    insert_date = models.DateTimeField(auto_now_add=True, null=True)
    insert_user = models.UUIDField(null=True, blank=True)
    update_date = models.DateTimeField(auto_now=True, null=True)
    update_user = models.UUIDField(null=True, blank=True)

    class Meta:
        db_table = 'v_dialplans'
        ordering = ['dialplan_order', 'dialplan_name']
        indexes = [
            models.Index(fields=['dialplan_context', 'dialplan_enabled', 'dialplan_order']),
            models.Index(fields=['tenant', 'dialplan_context']),
        ]

    def __str__(self):
        return f'{self.dialplan_name} ({self.dialplan_context})'


class DialplanDetail(models.Model):
    TAG_CHOICES = [('condition','Condition'),('action','Action'),('anti-action','Anti-Action')]
    dialplan_detail_uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        'core.Tenant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column='tenant_uuid',
        related_name='%(app_label)s_%(class)s_set',
    )
    domain = models.ForeignKey(Domain, on_delete=models.CASCADE, null=True, blank=True, db_column='domain_uuid')
    dialplan = models.ForeignKey(Dialplan, on_delete=models.CASCADE,
                                 db_column='dialplan_uuid', related_name='details')
    dialplan_detail_tag = models.CharField(max_length=32, choices=TAG_CHOICES, default='condition')
    dialplan_detail_type = models.CharField(max_length=128, blank=True, default='')
    dialplan_detail_data = models.CharField(max_length=4096, blank=True, default='')
    dialplan_detail_break = models.CharField(max_length=32, blank=True, default='')
    dialplan_detail_inline = models.BooleanField(default=False)
    dialplan_detail_group = models.IntegerField(default=0)
    dialplan_detail_order = models.IntegerField(default=10)
    insert_date = models.DateTimeField(auto_now_add=True, null=True)

    class Meta:
        db_table = 'v_dialplan_details'
        ordering = ['dialplan_detail_group', 'dialplan_detail_order']
        indexes = [
            models.Index(fields=['dialplan', 'dialplan_detail_group', 'dialplan_detail_order']),
        ]
