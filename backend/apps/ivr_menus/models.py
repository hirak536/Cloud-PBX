import uuid
from django.db import models
from core.models import Domain

class IvrMenu(models.Model):
    ivr_menu_uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        'core.Tenant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column='tenant_uuid',
        related_name='%(app_label)s_%(class)s_set',
    )
    domain = models.ForeignKey(Domain, on_delete=models.CASCADE, null=True, blank=True, db_column='domain_uuid')
    ivr_menu_name = models.CharField(max_length=255)
    ivr_menu_extension = models.CharField(max_length=255, blank=True)
    ivr_menu_language = models.CharField(max_length=10, default='en')
    ivr_menu_greet_long = models.CharField(max_length=255, blank=True)
    ivr_menu_greet_short = models.CharField(max_length=255, blank=True)
    ivr_menu_invalid_sound = models.CharField(max_length=255, blank=True)
    ivr_menu_exit_sound = models.CharField(max_length=255, blank=True)
    ivr_menu_confirm_macro = models.CharField(max_length=255, blank=True)
    ivr_menu_confirm_key = models.CharField(max_length=10, blank=True)
    ivr_menu_tts_engine = models.CharField(max_length=64, blank=True)
    ivr_menu_tts_voice = models.CharField(max_length=64, blank=True)
    ivr_menu_confirm_attempts = models.IntegerField(default=3)
    ivr_menu_timeout = models.IntegerField(default=3000)
    ivr_menu_inter_digit_timeout = models.IntegerField(default=2000)
    ivr_menu_max_failures = models.IntegerField(default=3)
    ivr_menu_max_timeouts = models.IntegerField(default=3)
    ivr_menu_digit_len = models.IntegerField(default=4)
    ivr_menu_direct_dial = models.CharField(max_length=10, blank=True)
    ivr_menu_ringback = models.CharField(max_length=255, blank=True)
    ivr_menu_cid_prefix = models.CharField(max_length=64, blank=True)
    ivr_menu_enabled = models.BooleanField(default=True)
    ivr_menu_description = models.TextField(blank=True)
    ivr_menu_playback_count = models.IntegerField(default=1)
    ivr_menu_loop_timeout = models.BooleanField(default=True)
    ivr_menu_loop_invalid = models.BooleanField(default=True)
    ivr_menu_allow_internal_dial = models.BooleanField(default=False)
    ivr_menu_allow_custom_codes = models.BooleanField(default=False)
    ivr_menu_allow_feature_codes = models.BooleanField(default=False)
    ivr_menu_internal_dial_invalid_type = models.CharField(max_length=32, blank=True, default='')
    ivr_menu_internal_dial_invalid_target_uuid = models.UUIDField(null=True, blank=True)
    ivr_menu_internal_dial_invalid_external_number = models.CharField(max_length=64, blank=True, default='')
    insert_date = models.DateTimeField(auto_now_add=True)
    insert_user = models.UUIDField(null=True, blank=True)
    update_date = models.DateTimeField(auto_now=True)
    update_user = models.UUIDField(null=True, blank=True)

    class Meta:
        db_table = 'v_ivr_menus'

    def __str__(self):
        return self.ivr_menu_name

    def save(self, *args, **kwargs):
        if not self.ivr_menu_extension:
            self.ivr_menu_extension = 'ivr_' + str(self.ivr_menu_uuid).replace('-', '')[:8]
        super().save(*args, **kwargs)

class IvrMenuOption(models.Model):
    ivr_menu_option_uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    ivr_menu = models.ForeignKey(IvrMenu, on_delete=models.CASCADE, related_name='options', db_column='ivr_menu_uuid')
    tenant = models.ForeignKey(
        'core.Tenant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column='tenant_uuid',
        related_name='%(app_label)s_%(class)s_set',
    )
    domain = models.ForeignKey(Domain, on_delete=models.CASCADE, null=True, blank=True, db_column='domain_uuid')
    ivr_menu_option_digits = models.CharField(max_length=64)
    ivr_menu_option_action = models.CharField(max_length=64, blank=True)
    ivr_menu_option_param = models.CharField(max_length=255, blank=True)
    ivr_menu_option_order = models.IntegerField(default=900)
    ivr_menu_option_description = models.TextField(blank=True)
    ivr_menu_option_dest_type = models.CharField(max_length=32, blank=True, default='')
    ivr_menu_option_dest_target_uuid = models.UUIDField(null=True, blank=True)
    ivr_menu_option_dest_external_number = models.CharField(max_length=64, blank=True, default='')
    insert_date = models.DateTimeField(auto_now_add=True)
    insert_user = models.UUIDField(null=True, blank=True)

    class Meta:
        db_table = 'v_ivr_menu_options'
        ordering = ['ivr_menu_option_order']
