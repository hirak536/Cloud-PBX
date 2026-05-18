import uuid
from django.db import models
from core.models import Domain


class ConferenceProfile(models.Model):
    conference_profile_uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        'core.Tenant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column='tenant_uuid',
        related_name='%(app_label)s_%(class)s_set',
    )
    domain = models.ForeignKey(Domain, on_delete=models.CASCADE, null=True, blank=True,
                               db_column='domain_uuid', related_name='conference_profiles')
    conference_profile_name = models.CharField(max_length=64)
    enabled = models.BooleanField(default=True)
    description = models.TextField(blank=True, default='')
    insert_date = models.DateTimeField(auto_now_add=True, null=True)

    class Meta:
        db_table = 'v_conference_profiles'

    def __str__(self):
        return self.conference_profile_name


class ConferenceProfileSetting(models.Model):
    conference_profile_setting_uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conference_profile = models.ForeignKey(ConferenceProfile, on_delete=models.CASCADE,
                                           db_column='conference_profile_uuid', related_name='settings')
    conference_profile_setting_name = models.CharField(max_length=128)
    conference_profile_setting_value = models.TextField(blank=True, default='')
    enabled = models.BooleanField(default=True)

    class Meta:
        db_table = 'v_conference_profile_settings'


class Conference(models.Model):
    conference_uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        'core.Tenant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column='tenant_uuid',
        related_name='%(app_label)s_%(class)s_set',
    )
    domain = models.ForeignKey(Domain, on_delete=models.CASCADE, db_column='domain_uuid', related_name='conferences')
    conference_name = models.CharField(max_length=128)
    conference_extension = models.CharField(max_length=32, blank=True, default='')
    conference_pin = models.CharField(max_length=16, blank=True, default='')
    conference_flags = models.CharField(max_length=256, blank=True, default='')
    conference_profile = models.ForeignKey(ConferenceProfile, on_delete=models.SET_NULL,
                                           null=True, blank=True, db_column='conference_profile_uuid')
    conference_max_members = models.IntegerField(default=0)
    conference_record = models.BooleanField(default=False)
    conference_record_file = models.CharField(max_length=512, blank=True, default='')
    conference_enabled = models.BooleanField(default=True)
    conference_description = models.TextField(blank=True, default='')
    insert_date = models.DateTimeField(auto_now_add=True, null=True)
    insert_user = models.UUIDField(null=True, blank=True)
    update_date = models.DateTimeField(auto_now=True, null=True)
    update_user = models.UUIDField(null=True, blank=True)

    class Meta:
        db_table = 'v_conferences'
        unique_together = [('tenant', 'conference_name')]

    def __str__(self):
        return self.conference_name


class ConferenceCenter(models.Model):
    conference_center_uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        'core.Tenant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column='tenant_uuid',
        related_name='%(app_label)s_%(class)s_set',
    )
    domain = models.ForeignKey(Domain, on_delete=models.CASCADE, db_column='domain_uuid', related_name='conference_centers')
    conference_center_name = models.CharField(max_length=128)
    conference_center_extension = models.CharField(max_length=32, blank=True, default='')
    conference_center_enabled = models.BooleanField(default=True)
    conference_center_description = models.TextField(blank=True, default='')

    class Meta:
        db_table = 'v_conference_centers'
