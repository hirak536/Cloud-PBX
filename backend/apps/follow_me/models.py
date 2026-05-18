import uuid
from django.db import models
from core.models import Domain

class FollowMe(models.Model):
    follow_me_uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        'core.Tenant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column='tenant_uuid',
        related_name='%(app_label)s_%(class)s_set',
    )
    domain = models.ForeignKey(Domain, on_delete=models.CASCADE, null=True, blank=True, db_column='domain_uuid')
    follow_me_name = models.CharField(max_length=255)
    follow_me_context = models.CharField(max_length=128, blank=True)
    follow_me_prompt = models.BooleanField(default=False)
    follow_me_cid_name_prefix = models.CharField(max_length=64, blank=True)
    follow_me_missed_call_email = models.CharField(max_length=255, blank=True)
    follow_me_description = models.TextField(blank=True)
    insert_date = models.DateTimeField(auto_now_add=True)
    insert_user = models.UUIDField(null=True, blank=True)
    update_date = models.DateTimeField(auto_now=True)
    update_user = models.UUIDField(null=True, blank=True)

    class Meta:
        db_table = 'v_follow_me'

    def __str__(self):
        return self.follow_me_name

class FollowMeDestination(models.Model):
    follow_me_destination_uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    follow_me = models.ForeignKey(FollowMe, on_delete=models.CASCADE, related_name='destinations', db_column='follow_me_uuid')
    tenant = models.ForeignKey(
        'core.Tenant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column='tenant_uuid',
        related_name='%(app_label)s_%(class)s_set',
    )
    domain = models.ForeignKey(Domain, on_delete=models.CASCADE, null=True, blank=True, db_column='domain_uuid')
    follow_me_destination_order = models.IntegerField(default=1)
    follow_me_destination = models.CharField(max_length=255)
    follow_me_delay = models.IntegerField(default=0)
    follow_me_timeout = models.IntegerField(default=30)
    follow_me_prompt = models.BooleanField(default=False)
    insert_date = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'v_follow_me_destinations'
        ordering = ['follow_me_destination_order']
