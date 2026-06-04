from django.contrib.auth import authenticate
from django.core.validators import URLValidator
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken

from .models import (
    AuditLog,
    DefaultSetting,
    Domain,
    DomainLimit,
    DomainSetting,
    Group,
    GroupPermission,
    Permission,
    Tenant,
    User,
    UserGroup,
    UserLog,
    UserSetting,
    UserTenantAccess,
)


# ---------------------------------------------------------------------------
# Tenant serializers
# ---------------------------------------------------------------------------

class TenantSerializer(serializers.ModelSerializer):
    domain_count = serializers.SerializerMethodField()
    fax_gateway_name = serializers.CharField(source='fax_gateway.gateway', read_only=True)
    default_gateway_name = serializers.CharField(source='default_gateway.gateway', read_only=True)

    class Meta:
        model = Tenant
        fields = [
            'tenant_uuid',
            'tenant_code',
            'tenant_name',
            'tenant_enabled',
            'tenant_status',
            'expiration_date',
            'max_channels',
            'max_extensions',
            'max_dids',
            'billing_code',
            'payment_type',
            'timezone',
            'allow_onnet_calls_from',
            'allow_onnet_calls_to',
            'recording_enabled',
            'provisioning_hostname',
            'voicemail_timeout',
            'push_notifications_enabled',
            'offline_poll_timeout',
            'default_gateway',
            'default_gateway_name',
            'default_gateway_priority',
            'fax_gateway',
            'fax_gateway_name',
            'description',
            'provisioning_webhook_url',
            'domain_count',
            'insert_date',
            'update_date',
        ]
        read_only_fields = ['tenant_uuid', 'insert_date', 'update_date', 'domain_count', 'fax_gateway_name', 'default_gateway_name']

    def get_domain_count(self, obj):
        return obj.domains.count()

    def validate_provisioning_webhook_url(self, value):
        if not value:
            return ''
        urls = [u.strip() for u in value.split(',') if u.strip()]
        validator = URLValidator()
        for url in urls:
            try:
                validator(url)
            except DjangoValidationError:
                raise serializers.ValidationError(f'Invalid URL: {url}')
        return ', '.join(urls)


class TenantListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for tenant list/select endpoints."""

    class Meta:
        model = Tenant
        fields = [
            'tenant_uuid',
            'tenant_code',
            'tenant_name',
            'tenant_enabled',
            'tenant_status',
            'default_gateway',
        ]
        read_only_fields = ['tenant_uuid', 'tenant_code', 'tenant_name', 'tenant_enabled', 'tenant_status', 'default_gateway']


# ---------------------------------------------------------------------------
# Domain serializers
# ---------------------------------------------------------------------------

class DomainListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for domain list endpoints."""

    class Meta:
        model = Domain
        fields = [
            'domain_uuid',
            'domain_name',
            'domain_parent_uuid',
            'domain_enabled',
            'insert_date',
            'update_date',
        ]
        read_only_fields = ['domain_uuid', 'insert_date', 'update_date']


class DomainSerializer(serializers.ModelSerializer):
    """Full domain serializer including description and audit fields."""
    tenant_code = serializers.CharField(source='tenant.tenant_code', read_only=True)

    class Meta:
        model = Domain
        fields = [
            'domain_uuid',
            'tenant',
            'tenant_code',
            'domain_name',
            'domain_parent_uuid',
            'domain_enabled',
            'domain_description',
            'insert_date',
            'insert_user',
            'update_date',
            'update_user',
        ]
        read_only_fields = ['domain_uuid', 'insert_date', 'update_date', 'tenant_code']


# ---------------------------------------------------------------------------
# Group serializers
# ---------------------------------------------------------------------------

class GroupSerializer(serializers.ModelSerializer):
    domain_name = serializers.CharField(source='domain.domain_name', read_only=True)
    tenant_code = serializers.CharField(source='tenant.tenant_code', read_only=True)

    class Meta:
        model = Group
        fields = [
            'group_uuid',
            'tenant',
            'tenant_code',
            'domain',
            'domain_name',
            'group_name',
            'group_level',
            'group_protected',
            'group_description',
            'insert_date',
            'update_date',
        ]
        read_only_fields = ['group_uuid', 'insert_date', 'update_date', 'tenant_code', 'domain_name']


# ---------------------------------------------------------------------------
# GroupPermission serializer
# ---------------------------------------------------------------------------

class GroupPermissionSerializer(serializers.ModelSerializer):
    group_name = serializers.CharField(source='group.group_name', read_only=True)

    class Meta:
        model = GroupPermission
        fields = [
            'group_permission_uuid',
            'domain',
            'group',
            'group_name',
            'permission_name',
            'permission_assigned',
            'insert_date',
        ]
        read_only_fields = ['group_permission_uuid', 'insert_date']


# ---------------------------------------------------------------------------
# UserGroup serializer
# ---------------------------------------------------------------------------

class UserGroupSerializer(serializers.ModelSerializer):
    group_name = serializers.CharField(source='group.group_name', read_only=True)
    group_level = serializers.IntegerField(source='group.group_level', read_only=True)

    class Meta:
        model = UserGroup
        fields = [
            'user_group_uuid',
            'domain',
            'user',
            'group',
            'group_name',
            'group_level',
            'insert_date',
        ]
        read_only_fields = ['user_group_uuid', 'insert_date']


class UserGroupNestedSerializer(serializers.ModelSerializer):
    """Minimal nested representation used inside UserSerializer."""
    group_name = serializers.CharField(source='group.group_name', read_only=True)
    group_uuid = serializers.UUIDField(source='group.group_uuid', read_only=True)
    group_level = serializers.IntegerField(source='group.group_level', read_only=True)

    class Meta:
        model = UserGroup
        fields = ['user_group_uuid', 'group_uuid', 'group_name', 'group_level']


# ---------------------------------------------------------------------------
# UserSetting serializer
# ---------------------------------------------------------------------------

class UserSettingSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserSetting
        fields = [
            'user_setting_uuid',
            'domain',
            'user',
            'user_setting_category',
            'user_setting_subcategory',
            'user_setting_name',
            'user_setting_value',
            'user_setting_order',
            'user_setting_enabled',
            'user_setting_description',
            'insert_date',
        ]
        read_only_fields = ['user_setting_uuid', 'insert_date']


# ---------------------------------------------------------------------------
# User serializers
# ---------------------------------------------------------------------------

class UserSerializer(serializers.ModelSerializer):
    """Read serializer — excludes password, includes nested groups and tenant access."""
    user_groups = UserGroupNestedSerializer(many=True, read_only=True)
    domain_name = serializers.CharField(source='domain.domain_name', read_only=True)
    tenant_code = serializers.CharField(source='tenant.tenant_code', read_only=True)
    admin_tenants = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'user_uuid',
            'tenant',
            'tenant_code',
            'domain',
            'domain_name',
            'username',
            'full_name',
            'user_email',
            'user_enabled',
            'user_status',
            'api_key',
            'is_staff',
            'is_superuser',
            'must_change_password',
            'admin_tenants',
            'allowed_pages',
            'allowed_fax_uuids',
            'user_groups',
            'insert_date',
            'update_date',
        ]
        read_only_fields = ['user_uuid', 'insert_date', 'update_date', 'tenant_code', 'domain_name', 'admin_tenants']

    def get_admin_tenants(self, obj):
        return [
            {
                'tenant_uuid': str(t.tenant_uuid),
                'tenant_code': t.tenant_code,
                'tenant_name': t.tenant_name,
            }
            for t in obj.admin_tenants.all()
        ]


class UserCreateSerializer(serializers.ModelSerializer):
    """Write serializer — handles password hashing via set_password."""
    password = serializers.CharField(
        write_only=True,
        required=True,
        style={'input_type': 'password'},
        min_length=8,
    )
    password_confirm = serializers.CharField(
        write_only=True,
        required=True,
        style={'input_type': 'password'},
    )
    user_email = serializers.EmailField(required=True)
    admin_tenant_uuids = serializers.ListField(
        child=serializers.UUIDField(),
        required=False,
        write_only=True,
        default=list,
    )

    class Meta:
        model = User
        fields = [
            'user_uuid',
            'tenant',
            'domain',
            'username',
            'full_name',
            'password',
            'password_confirm',
            'user_email',
            'user_enabled',
            'user_status',
            'is_staff',
            'is_superuser',
            'must_change_password',
            'admin_tenant_uuids',
            'allowed_pages',
            'allowed_fax_uuids',
        ]
        read_only_fields = ['user_uuid']
        # Disable auto-generated UniqueTogetherValidator for (tenant, username).
        # DRF's enforce_required_fields() raises "tenant required" even when
        # tenant is nullable. We check uniqueness manually below.
        validators = []

    def validate(self, attrs):
        if attrs.get('password') != attrs.get('password_confirm'):
            raise serializers.ValidationError({'password_confirm': 'Passwords do not match.'})
        # Manual (tenant, username) uniqueness check that handles null tenant.
        tenant = attrs.get('tenant')
        username = attrs.get('username')
        if username:
            qs = User.objects.filter(username=username)
            qs = qs.filter(tenant=tenant) if tenant is not None else qs.filter(tenant__isnull=True)
            if qs.exists():
                raise serializers.ValidationError(
                    {'username': 'A user with this username already exists for this tenant.'}
                )
        return attrs

    def create(self, validated_data):
        validated_data.pop('password_confirm', None)
        admin_tenant_uuids = validated_data.pop('admin_tenant_uuids', [])
        password = validated_data.pop('password')
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        if admin_tenant_uuids:
            user.admin_tenants.set(admin_tenant_uuids)
        return user

    def update(self, instance, validated_data):
        validated_data.pop('password_confirm', None)
        admin_tenant_uuids = validated_data.pop('admin_tenant_uuids', None)
        password = validated_data.pop('password', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if password:
            instance.set_password(password)
        instance.save()
        if admin_tenant_uuids is not None:
            instance.admin_tenants.set(admin_tenant_uuids)
        return instance


class UserUpdateSerializer(serializers.ModelSerializer):
    """Partial-update serializer — password is optional."""
    password = serializers.CharField(
        write_only=True,
        required=False,
        allow_blank=True,
        style={'input_type': 'password'},
        min_length=8,
    )
    admin_tenant_uuids = serializers.ListField(
        child=serializers.UUIDField(),
        required=False,
        write_only=True,
    )

    class Meta:
        model = User
        fields = [
            'user_uuid',
            'tenant',
            'domain',
            'username',
            'full_name',
            'password',
            'user_email',
            'user_enabled',
            'user_status',
            'is_staff',
            'is_superuser',
            'must_change_password',
            'admin_tenant_uuids',
            'allowed_pages',
            'allowed_fax_uuids',
        ]
        read_only_fields = ['user_uuid']
        validators = []

    def validate(self, attrs):
        # Uniqueness check on username change, excluding the current instance.
        username = attrs.get('username')
        if username and self.instance and username != self.instance.username:
            tenant = attrs.get('tenant', self.instance.tenant)
            qs = User.objects.filter(username=username)
            qs = qs.filter(tenant=tenant) if tenant is not None else qs.filter(tenant__isnull=True)
            qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError(
                    {'username': 'A user with this username already exists for this tenant.'}
                )
        return attrs

    def update(self, instance, validated_data):
        admin_tenant_uuids = validated_data.pop('admin_tenant_uuids', None)
        password = validated_data.pop('password', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if password:
            instance.set_password(password)
        instance.save()
        if admin_tenant_uuids is not None:
            instance.admin_tenants.set(admin_tenant_uuids)
        return instance


# ---------------------------------------------------------------------------
# UserLog serializer
# ---------------------------------------------------------------------------

class UserLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserLog
        fields = [
            'user_log_uuid',
            'domain',
            'user',
            'username',
            'user_log_type',
            'user_log_ipv4',
            'user_log_agent',
            'user_log_timestamp',
            'user_log_message',
        ]
        read_only_fields = [
            'user_log_uuid',
            'user_log_timestamp',
        ]


# ---------------------------------------------------------------------------
# Settings serializers
# ---------------------------------------------------------------------------

class DefaultSettingSerializer(serializers.ModelSerializer):
    class Meta:
        model = DefaultSetting
        fields = [
            'default_setting_uuid',
            'app_uuid',
            'default_setting_category',
            'default_setting_subcategory',
            'default_setting_name',
            'default_setting_value',
            'default_setting_order',
            'default_setting_enabled',
            'default_setting_description',
            'insert_date',
            'update_date',
        ]
        read_only_fields = ['default_setting_uuid', 'insert_date', 'update_date']


class DomainSettingSerializer(serializers.ModelSerializer):
    domain_name = serializers.CharField(source='domain.domain_name', read_only=True)

    class Meta:
        model = DomainSetting
        fields = [
            'domain_setting_uuid',
            'domain',
            'domain_name',
            'app_uuid',
            'domain_setting_category',
            'domain_setting_subcategory',
            'domain_setting_name',
            'domain_setting_value',
            'domain_setting_order',
            'domain_setting_enabled',
            'domain_setting_description',
            'insert_date',
            'update_date',
        ]
        read_only_fields = ['domain_setting_uuid', 'insert_date', 'update_date']


# ---------------------------------------------------------------------------
# Auth serializers
# ---------------------------------------------------------------------------

class LoginSerializer(serializers.Serializer):
    """Validates login credentials.

    Accepts username + optional tenant_code (preferred) or domain (legacy).
    Also supports 'user@domain' format in the username field.
    On success, attaches the authenticated user instance to validated_data.
    """
    username = serializers.CharField(max_length=254)
    password = serializers.CharField(
        max_length=128,
        write_only=True,
        style={'input_type': 'password'},
    )
    tenant_code = serializers.CharField(max_length=32, required=False, allow_blank=True)
    domain = serializers.CharField(max_length=128, required=False, allow_blank=True)

    def validate(self, attrs):
        username = attrs.get('username', '').strip()
        password = attrs.get('password', '')
        tenant_code = attrs.get('tenant_code', '').strip() or None
        domain = attrs.get('domain', '').strip() or None

        request = self.context.get('request')
        user = authenticate(
            request=request,
            username=username,
            password=password,
            tenant_code=tenant_code,
            domain=domain,
        )

        if user is None:
            raise serializers.ValidationError(
                {'non_field_errors': ['Invalid username or password.']},
                code='authentication_failed',
            )

        if not user.user_enabled:
            raise serializers.ValidationError(
                {'non_field_errors': ['This account has been disabled. Contact your administrator.']},
                code='account_disabled',
            )

        attrs['user'] = user
        return attrs


class TokenRefreshResponseSerializer(serializers.Serializer):
    """Documents the shape of the response from simplejwt's TokenRefreshView."""
    access = serializers.CharField(read_only=True)


class MeSerializer(serializers.ModelSerializer):
    """Serializer for the /auth/me/ endpoint."""
    user_groups = UserGroupNestedSerializer(many=True, read_only=True)
    domain_name = serializers.CharField(source='domain.domain_name', read_only=True)
    tenant_code = serializers.CharField(source='tenant.tenant_code', read_only=True)
    tenant_name = serializers.CharField(source='tenant.tenant_name', read_only=True)
    permissions = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'user_uuid',
            'tenant',
            'tenant_code',
            'tenant_name',
            'domain',
            'domain_name',
            'username',
            'full_name',
            'user_email',
            'user_enabled',
            'user_status',
            'is_staff',
            'is_superuser',
            'must_change_password',
            'user_groups',
            'permissions',
            'allowed_pages',
            'allowed_fax_uuids',
            'insert_date',
            'update_date',
        ]
        read_only_fields = fields

    def get_permissions(self, obj):
        return sorted(obj.get_permission_names())


# ---------------------------------------------------------------------------
# AuditLog serializer
# ---------------------------------------------------------------------------

class AuditLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = AuditLog
        fields = [
            'audit_log_uuid',
            'tenant',
            'domain',
            'user',
            'username',
            'action',
            'resource_type',
            'resource_uuid',
            'resource_name',
            'changes',
            'ip_address',
            'user_agent',
            'timestamp',
        ]
        read_only_fields = fields


# ---------------------------------------------------------------------------
# Permission serializer (v_permissions catalogue)
# ---------------------------------------------------------------------------

class PermissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Permission
        fields = ['permission_uuid', 'permission_name', 'permission_description']
        read_only_fields = ['permission_uuid']


# ---------------------------------------------------------------------------
# DomainLimit serializer
# ---------------------------------------------------------------------------

class DomainLimitSerializer(serializers.ModelSerializer):
    domain_name = serializers.CharField(source='domain.domain_name', read_only=True)

    class Meta:
        model = DomainLimit
        fields = [
            'domain_limit_uuid',
            'domain',
            'domain_name',
            'domain_limit_name',
            'domain_limit_value',
            'domain_limit_enabled',
            'domain_limit_description',
        ]
        read_only_fields = ['domain_limit_uuid']
