import uuid
from django.db import models


class SipProfile(models.Model):
    sip_profile_uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sip_profile_name = models.CharField(max_length=64, unique=True)
    sip_profile_hostname = models.CharField(max_length=256, blank=True, default='')
    sip_profile_enabled = models.BooleanField(default=True)
    sip_profile_description = models.TextField(blank=True, default='')
    insert_date = models.DateTimeField(auto_now_add=True, null=True)
    insert_user = models.UUIDField(null=True, blank=True)
    update_date = models.DateTimeField(auto_now=True, null=True)
    update_user = models.UUIDField(null=True, blank=True)

    class Meta:
        db_table = 'v_sip_profiles'

    def __str__(self):
        return self.sip_profile_name


class SipProfileSetting(models.Model):
    sip_profile_setting_uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sip_profile = models.ForeignKey(SipProfile, on_delete=models.CASCADE,
                                    db_column='sip_profile_uuid', related_name='settings')
    sip_profile_setting_name = models.CharField(max_length=128)
    sip_profile_setting_value = models.TextField(blank=True, default='')
    sip_profile_setting_enabled = models.BooleanField(default=True)
    sip_profile_setting_description = models.TextField(blank=True, default='')
    insert_date = models.DateTimeField(auto_now_add=True, null=True)

    class Meta:
        db_table = 'v_sip_profile_settings'


class SipProfileDomain(models.Model):
    sip_profile_domain_uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sip_profile = models.ForeignKey(SipProfile, on_delete=models.CASCADE,
                                    db_column='sip_profile_uuid', related_name='domains')
    sip_profile_domain_name = models.CharField(max_length=128)
    sip_profile_domain_alias = models.BooleanField(default=False)
    sip_profile_domain_parse = models.BooleanField(default=False)

    class Meta:
        db_table = 'v_sip_profile_domains'
