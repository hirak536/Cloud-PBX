import re
import uuid

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone


def _generate_tenant_code(name):
    """
    Generate a short tenant code from tenant_name:
      1 word  → first 3 letters          e.g. "Acme"           → "ACM"
      2 words → 1 letter + 2 letters     e.g. "Acme Corp"      → "ACO"
      3+ words→ 1 letter each (3 words)  e.g. "Acme Corp Ltd"  → "ACL"
    Always uppercase, alphanumeric only, max 32 chars.
    """
    words = [re.sub(r'[^a-zA-Z0-9]', '', w) for w in name.strip().split()]
    words = [w for w in words if w]
    if not words:
        return ''
    if len(words) == 1:
        code = words[0][:3]
    elif len(words) == 2:
        code = words[0][:1] + words[1][:2]
    else:
        code = words[0][:1] + words[1][:1] + words[2][:1]
    return code.upper()


def _unique_tenant_code(name, exclude_pk=None):
    """Return a unique tenant_code derived from name, appending numeric suffix if needed."""
    base = _generate_tenant_code(name)
    if not base:
        base = 'T'
    code = base
    suffix = 1
    qs = Tenant.objects.filter(tenant_code=code)
    if exclude_pk:
        qs = qs.exclude(pk=exclude_pk)
    while qs.exists():
        code = f'{base}{suffix}'
        suffix += 1
        qs = Tenant.objects.filter(tenant_code=code)
        if exclude_pk:
            qs = qs.exclude(pk=exclude_pk)
    return code


class Tenant(models.Model):
    PAYMENT_TYPE_CHOICES = [
        ('prepaid', 'Prepaid'),
        ('postpaid', 'Postpaid'),
    ]
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('suspended', 'Suspended'),
        ('expired', 'Expired'),
    ]

    tenant_uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant_code = models.CharField(
        max_length=32,
        unique=True,
        blank=True,
        help_text='Auto-generated from tenant name if left blank.',
    )
    tenant_name = models.CharField(max_length=128)
    tenant_enabled = models.BooleanField(default=True)
    tenant_status = models.CharField(max_length=16, choices=STATUS_CHOICES, default='active')
    expiration_date = models.DateField(null=True, blank=True)

    # Resource limits
    max_channels = models.IntegerField(null=True, blank=True)
    max_extensions = models.IntegerField(null=True, blank=True)
    max_dids = models.IntegerField(null=True, blank=True)

    # Billing
    billing_code = models.CharField(max_length=64, blank=True, default='')
    payment_type = models.CharField(max_length=16, choices=PAYMENT_TYPE_CHOICES, default='postpaid')

    # Call features
    timezone = models.CharField(max_length=64, default='UTC')
    allow_onnet_calls_from = models.BooleanField(default=True)
    allow_onnet_calls_to = models.BooleanField(default=True)
    recording_enabled = models.BooleanField(default=True)
    provisioning_hostname = models.CharField(max_length=256, blank=True, default='')

    # Voicemail settings
    voicemail_timeout = models.IntegerField(
        default=120,
        help_text='Maximum voicemail recording length in seconds.',
    )

    # Mobile push notification settings
    push_notifications_enabled = models.BooleanField(default=False)
    offline_poll_timeout = models.PositiveSmallIntegerField(
        default=30,
        help_text='Seconds to wait for an offline extension to register before forwarding (1–120).',
    )

    # Default outbound gateway
    default_gateway = models.ForeignKey(
        'gateways.Gateway',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column='default_gateway_uuid',
        related_name='default_tenants',
        help_text='Default gateway used for outbound calls.',
    )
    default_gateway_priority = models.IntegerField(
        default=10,
        help_text='Lower number = higher priority (1 is highest).',
    )

    # Fax settings
    fax_gateway = models.ForeignKey(
        'gateways.Gateway',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column='fax_gateway_uuid',
        related_name='fax_tenants',
        help_text='Default gateway used for outbound fax transmission.',
    )

    description = models.TextField(blank=True, default='')

    # Provisioning webhook: called once on tenant creation with the generated API key.
    # Accepts one URL or multiple URLs separated by commas; all are POSTed.
    provisioning_webhook_url = models.TextField(
        blank=True,
        default='',
        help_text='Optional URL(s) to POST the generated API key to when this tenant is created. Separate multiple URLs with commas.',
    )

    @property
    def provisioning_webhook_urls(self):
        """Return the configured webhook URL(s) as a clean list."""
        raw = self.provisioning_webhook_url or ''
        return [u.strip() for u in raw.split(',') if u.strip()]

    insert_date = models.DateTimeField(auto_now_add=True, null=True)
    insert_user = models.UUIDField(null=True, blank=True)
    update_date = models.DateTimeField(auto_now=True, null=True)
    update_user = models.UUIDField(null=True, blank=True)

    class Meta:
        db_table = 'v_tenants'

    def __str__(self):
        return f'{self.tenant_code} / {self.tenant_name}'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._original_tenant_name = self.tenant_name
        self._original_tenant_code = self.tenant_code

    def save(self, *args, **kwargs):
        if not self.tenant_code:
            self.tenant_code = _unique_tenant_code(self.tenant_name, exclude_pk=self.pk)
        super().save(*args, **kwargs)


class Domain(models.Model):
    domain_uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column='tenant_uuid',
        related_name='domains',
    )
    domain_name = models.CharField(max_length=128, unique=True)
    domain_universal = models.BooleanField(
        default=False,
        help_text='If enabled, this domain is shared by all tenants.',
    )
    domain_parent_uuid = models.UUIDField(null=True, blank=True)
    domain_enabled = models.BooleanField(default=True)
    domain_description = models.TextField(blank=True, default='')
    insert_date = models.DateTimeField(auto_now_add=True, null=True)
    insert_user = models.UUIDField(null=True, blank=True)
    update_date = models.DateTimeField(auto_now=True, null=True)
    update_user = models.UUIDField(null=True, blank=True)

    class Meta:
        db_table = 'v_domains'

    def __str__(self):
        return self.domain_name


class DomainSetting(models.Model):
    domain_setting_uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    domain = models.ForeignKey(
        Domain,
        on_delete=models.CASCADE,
        db_column='domain_uuid',
        related_name='settings',
    )
    app_uuid = models.UUIDField(null=True, blank=True)
    domain_setting_category = models.CharField(max_length=128)
    domain_setting_subcategory = models.CharField(max_length=256, blank=True, default='')
    domain_setting_name = models.CharField(max_length=64, default='text')
    domain_setting_value = models.TextField(blank=True, default='')
    domain_setting_order = models.IntegerField(default=0)
    domain_setting_enabled = models.BooleanField(default=True)
    domain_setting_description = models.TextField(blank=True, default='')
    insert_date = models.DateTimeField(auto_now_add=True, null=True)
    insert_user = models.UUIDField(null=True, blank=True)
    update_date = models.DateTimeField(auto_now=True, null=True)
    update_user = models.UUIDField(null=True, blank=True)

    class Meta:
        db_table = 'v_domain_settings'

    def __str__(self):
        return f'{self.domain_id} / {self.domain_setting_category} / {self.domain_setting_subcategory}'


class DefaultSetting(models.Model):
    default_setting_uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    app_uuid = models.UUIDField(null=True, blank=True)
    default_setting_category = models.CharField(max_length=128)
    default_setting_subcategory = models.CharField(max_length=256, blank=True, default='')
    default_setting_name = models.CharField(max_length=64, default='text')
    default_setting_value = models.TextField(blank=True, default='')
    default_setting_order = models.IntegerField(default=0)
    default_setting_enabled = models.BooleanField(default=True)
    default_setting_description = models.TextField(blank=True, default='')
    insert_date = models.DateTimeField(auto_now_add=True, null=True)
    insert_user = models.UUIDField(null=True, blank=True)
    update_date = models.DateTimeField(auto_now=True, null=True)
    update_user = models.UUIDField(null=True, blank=True)

    class Meta:
        db_table = 'v_default_settings'

    def __str__(self):
        return f'{self.default_setting_category} / {self.default_setting_subcategory}'


class Group(models.Model):
    group_uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column='tenant_uuid',
        related_name='groups',
    )
    domain = models.ForeignKey(
        Domain,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        db_column='domain_uuid',
        related_name='groups',
    )
    group_name = models.CharField(max_length=64)
    group_level = models.IntegerField(default=0)
    group_protected = models.BooleanField(default=False)
    group_description = models.TextField(blank=True, default='')
    insert_date = models.DateTimeField(auto_now_add=True, null=True)
    insert_user = models.UUIDField(null=True, blank=True)
    update_date = models.DateTimeField(auto_now=True, null=True)
    update_user = models.UUIDField(null=True, blank=True)

    class Meta:
        db_table = 'v_groups'
        unique_together = [('tenant', 'group_name')]

    def __str__(self):
        return self.group_name


class Permission(models.Model):
    permission_uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    permission_name = models.CharField(max_length=128, unique=True)
    permission_description = models.TextField(blank=True, default='')

    class Meta:
        db_table = 'v_permissions'

    def __str__(self):
        return self.permission_name


class GroupPermission(models.Model):
    group_permission_uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column='tenant_uuid',
        related_name='group_permissions',
    )
    domain = models.ForeignKey(
        Domain,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        db_column='domain_uuid',
    )
    group = models.ForeignKey(
        Group,
        on_delete=models.CASCADE,
        db_column='group_uuid',
        to_field='group_uuid',
        related_name='permissions',
    )
    permission_name = models.CharField(max_length=128)
    permission_assigned = models.BooleanField(default=True)
    insert_date = models.DateTimeField(auto_now_add=True, null=True)
    insert_user = models.UUIDField(null=True, blank=True)

    class Meta:
        db_table = 'v_group_permissions'
        unique_together = [('tenant', 'group', 'permission_name')]

    def __str__(self):
        return f'{self.group_id} / {self.permission_name}'


class UserManager(BaseUserManager):
    def create_user(self, username, password=None, **extra_fields):
        if not username:
            raise ValueError('Username is required')
        user = self.model(username=username, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, username, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')
        return self.create_user(username, password, **extra_fields)


class User(AbstractBaseUser):
    user_uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column='tenant_uuid',
        related_name='users',
    )
    domain = models.ForeignKey(
        Domain,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        db_column='domain_uuid',
        related_name='users',
    )
    username = models.CharField(max_length=254)
    user_enabled = models.BooleanField(default=True)
    user_status = models.CharField(max_length=32, blank=True, default='')
    user_email = models.EmailField(blank=True, default='')
    user_totp_secret = models.CharField(max_length=64, blank=True, default='')
    api_key = models.CharField(max_length=128, blank=True, default='', db_index=True)
    is_staff = models.BooleanField(default=False)
    is_superuser = models.BooleanField(default=False)
    admin_tenants = models.ManyToManyField(
        Tenant,
        through='UserTenantAccess',
        related_name='admin_users',
        blank=True,
    )
    full_name = models.CharField(max_length=256, blank=True, default='')
    must_change_password = models.BooleanField(default=False)
    # Per-user page grants. Only consulted for standard (non-staff) users; admins
    # and superusers get full role-based access regardless of this list.
    # Empty list = no extra pages granted; null/absent = treated as empty.
    allowed_pages = models.JSONField(default=list, blank=True)
    # Per-user fax-box scoping. List of Fax box UUIDs (as strings) this user may
    # see. Empty list = NO restriction (all fax boxes in their tenant). Only
    # consulted for standard (non-staff) users; admins/superusers see all.
    allowed_fax_uuids = models.JSONField(default=list, blank=True)
    insert_date = models.DateTimeField(auto_now_add=True, null=True)
    insert_user = models.UUIDField(null=True, blank=True)
    update_date = models.DateTimeField(auto_now=True, null=True)
    update_user = models.UUIDField(null=True, blank=True)

    USERNAME_FIELD = 'username'
    REQUIRED_FIELDS = []

    objects = UserManager()

    class Meta:
        db_table = 'v_users'
        unique_together = [('tenant', 'username')]

    def __str__(self):
        if self.tenant_id:
            return f'{self.username}@{self.tenant}'
        if self.domain_id:
            return f'{self.username}@{self.domain}'
        return self.username

    def has_perm(self, perm, obj=None):
        return self.is_superuser

    def has_module_perms(self, app_label):
        return self.is_superuser

    def get_permission_names(self):
        """Return a set of permission_name strings for this user across all their groups."""
        return set(
            GroupPermission.objects.filter(
                group__user_groups__user=self,
                permission_assigned=True,
            ).values_list('permission_name', flat=True)
        )

    def fax_box_scope(self):
        """Return the list of Fax box UUIDs this user is restricted to, or None
        for no restriction. Admins/superusers and an empty list both mean None
        (see all fax boxes in their tenant)."""
        if self.is_staff or self.is_superuser:
            return None
        uuids = self.allowed_fax_uuids or []
        return [str(u) for u in uuids] if uuids else None


class UserGroup(models.Model):
    user_group_uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column='tenant_uuid',
        related_name='user_groups',
    )
    domain = models.ForeignKey(
        Domain,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        db_column='domain_uuid',
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        db_column='user_uuid',
        to_field='user_uuid',
        related_name='user_groups',
    )
    group = models.ForeignKey(
        Group,
        on_delete=models.CASCADE,
        db_column='group_uuid',
        to_field='group_uuid',
        related_name='user_groups',
    )
    insert_date = models.DateTimeField(auto_now_add=True, null=True)

    class Meta:
        db_table = 'v_user_groups'
        unique_together = [('user', 'group')]

    def __str__(self):
        return f'{self.user_id} / {self.group_id}'


class UserTenantAccess(models.Model):
    """Maps admin users to the tenants they can manage (multi-tenant admin support)."""
    user_tenant_access_uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        db_column='user_uuid',
        to_field='user_uuid',
        related_name='tenant_accesses',
    )
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        db_column='tenant_uuid',
        to_field='tenant_uuid',
        related_name='admin_accesses',
    )
    insert_date = models.DateTimeField(auto_now_add=True, null=True)

    class Meta:
        db_table = 'v_user_tenant_access'
        unique_together = [('user', 'tenant')]

    def __str__(self):
        return f'{self.user_id} / {self.tenant_id}'


class UserSetting(models.Model):
    user_setting_uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column='tenant_uuid',
        related_name='user_settings',
    )
    domain = models.ForeignKey(
        Domain,
        on_delete=models.CASCADE,
        null=True,
        db_column='domain_uuid',
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        db_column='user_uuid',
        to_field='user_uuid',
        related_name='settings',
    )
    user_setting_category = models.CharField(max_length=128)
    user_setting_subcategory = models.CharField(max_length=256, blank=True, default='')
    user_setting_name = models.CharField(max_length=64, default='text')
    user_setting_value = models.TextField(blank=True, default='')
    user_setting_order = models.IntegerField(default=0)
    user_setting_enabled = models.BooleanField(default=True)
    user_setting_description = models.TextField(blank=True, default='')
    insert_date = models.DateTimeField(auto_now_add=True, null=True)

    class Meta:
        db_table = 'v_user_settings'

    def __str__(self):
        return f'{self.user_id} / {self.user_setting_category} / {self.user_setting_subcategory}'


class UserLog(models.Model):
    LOG_TYPES = [
        ('login', 'Login'),
        ('logout', 'Logout'),
        ('failed', 'Failed Login'),
        ('session', 'Session'),
    ]

    user_log_uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column='tenant_uuid',
        related_name='user_logs',
    )
    domain = models.ForeignKey(
        Domain,
        on_delete=models.SET_NULL,
        null=True,
        db_column='domain_uuid',
    )
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        db_column='user_uuid',
        to_field='user_uuid',
        related_name='logs',
    )
    username = models.CharField(max_length=254, blank=True, default='')
    user_log_type = models.CharField(max_length=32, choices=LOG_TYPES, default='login')
    user_log_ipv4 = models.GenericIPAddressField(protocol='IPv4', null=True, blank=True)
    user_log_agent = models.TextField(blank=True, default='')
    user_log_timestamp = models.DateTimeField(default=timezone.now)
    user_log_message = models.TextField(blank=True, default='')

    class Meta:
        db_table = 'v_user_logs'
        ordering = ['-user_log_timestamp']

    def __str__(self):
        return f'{self.user_log_type} / {self.username} / {self.user_log_timestamp}'


class AuditLog(models.Model):
    ACTION_CHOICES = [
        ('create', 'Create'),
        ('update', 'Update'),
        ('delete', 'Delete'),
    ]

    audit_log_uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column='tenant_uuid',
        related_name='audit_logs',
    )
    domain = models.ForeignKey(
        Domain,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column='domain_uuid',
    )
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column='user_uuid',
        to_field='user_uuid',
        related_name='audit_logs',
    )
    username = models.CharField(max_length=254, blank=True, default='')
    action = models.CharField(max_length=16, choices=ACTION_CHOICES)
    resource_type = models.CharField(max_length=128)
    resource_uuid = models.CharField(max_length=64, blank=True, default='')
    resource_name = models.CharField(max_length=256, blank=True, default='')
    changes = models.JSONField(null=True, blank=True)
    ip_address = models.GenericIPAddressField(protocol='IPv4', null=True, blank=True)
    user_agent = models.TextField(blank=True, default='')
    timestamp = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = 'v_audit_logs'
        ordering = ['-timestamp']

    def __str__(self):
        return f'{self.action} / {self.resource_type} / {self.username} / {self.timestamp}'


class DomainLimit(models.Model):
    domain_limit_uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column='tenant_uuid',
        related_name='domain_limits',
    )
    domain = models.ForeignKey(
        Domain,
        on_delete=models.CASCADE,
        db_column='domain_uuid',
        related_name='limits',
    )
    domain_limit_name = models.CharField(max_length=128)
    domain_limit_value = models.TextField(blank=True, default='')
    domain_limit_enabled = models.BooleanField(default=True)
    domain_limit_description = models.TextField(blank=True, default='')

    class Meta:
        db_table = 'v_domain_limits'

    def __str__(self):
        return f'{self.domain_id} / {self.domain_limit_name}'


# ── Signals ──────────────────────────────────────────────────────────────────

@receiver(post_save, sender=Tenant)
def tenant_identity_changed(sender, instance, created, **kwargs):
    """Fire a webhook when tenant_name or tenant_code changes."""
    if created:
        return
    name_changed = instance.tenant_name != instance._original_tenant_name
    code_changed = instance.tenant_code != instance._original_tenant_code
    if not (name_changed or code_changed):
        return
    try:
        from apps.client_api.tasks import fire_webhook_event
        fire_webhook_event.delay(
            str(instance.tenant_uuid),
            'tenant.updated',
            str(instance.tenant_uuid),
            {
                'tenant_name': instance.tenant_name,
                'tenant_code': instance.tenant_code,
            },
        )
    except Exception:
        pass


@receiver(post_save, sender=Tenant)
def auto_assign_universal_domain(sender, instance, created, **kwargs):
    """
    When a new Tenant is created, automatically assign any universal domain
    (domain_universal=True, tenant=NULL) to that tenant.
    """
    if not created:
        return
    universal = Domain.objects.filter(
        domain_universal=True,
        domain_enabled=True,
        tenant__isnull=True,
    ).first()
    if universal:
        universal.tenant = instance
        universal.save(update_fields=['tenant'])
