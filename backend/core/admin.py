from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _

from .models import (
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
)


@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):
    list_display = (
        'tenant_code',
        'tenant_name',
        'tenant_status',
        'tenant_enabled',
        'max_extensions',
        'max_dids',
        'payment_type',
        'insert_date',
    )
    list_filter = ('tenant_enabled', 'tenant_status', 'payment_type')
    search_fields = ('tenant_code', 'tenant_name', 'billing_code')
    ordering = ('tenant_code',)
    readonly_fields = ('tenant_uuid', 'tenant_code', 'insert_date', 'update_date')
    fieldsets = (
        (None, {
            'fields': (
                'tenant_uuid', 'tenant_name', 'tenant_code',
                'tenant_enabled', 'tenant_status', 'expiration_date',
            ),
        }),
        (_('Resource Limits'), {
            'fields': ('max_channels', 'max_extensions', 'max_dids'),
        }),
        (_('Billing'), {
            'fields': ('billing_code', 'payment_type'),
        }),
        (_('Call Features'), {
            'fields': (
                'timezone', 'recording_enabled',
                'allow_onnet_calls_from', 'allow_onnet_calls_to',
                'provisioning_hostname',
            ),
        }),
        (_('Description'), {
            'fields': ('description',),
            'classes': ('collapse',),
        }),
        (_('Audit'), {
            'fields': ('insert_date', 'insert_user', 'update_date', 'update_user'),
            'classes': ('collapse',),
        }),
    )


@admin.register(Domain)
class DomainAdmin(admin.ModelAdmin):
    list_display = (
        'domain_name',
        'tenant',
        'domain_universal',
        'domain_enabled',
        'insert_date',
    )
    list_filter = ('domain_enabled', 'domain_universal', 'tenant')
    search_fields = ('domain_name', 'domain_description', 'tenant__tenant_code')
    ordering = ('domain_name',)
    readonly_fields = ('domain_uuid', 'insert_date', 'update_date')
    raw_id_fields = ('tenant',)
    fieldsets = (
        (None, {
            'fields': ('domain_uuid', 'tenant', 'domain_name', 'domain_universal', 'domain_parent_uuid', 'domain_enabled'),
        }),
        (_('Description'), {
            'fields': ('domain_description',),
            'classes': ('collapse',),
        }),
        (_('Audit'), {
            'fields': ('insert_date', 'insert_user', 'update_date', 'update_user'),
            'classes': ('collapse',),
        }),
    )


@admin.register(DomainSetting)
class DomainSettingAdmin(admin.ModelAdmin):
    list_display = (
        'domain',
        'domain_setting_category',
        'domain_setting_subcategory',
        'domain_setting_name',
        'domain_setting_value',
        'domain_setting_enabled',
        'domain_setting_order',
    )
    list_filter = ('domain_setting_enabled', 'domain_setting_category', 'domain')
    search_fields = (
        'domain__domain_name',
        'domain_setting_category',
        'domain_setting_subcategory',
        'domain_setting_name',
        'domain_setting_value',
    )
    ordering = ('domain', 'domain_setting_category', 'domain_setting_subcategory', 'domain_setting_order')
    readonly_fields = ('domain_setting_uuid', 'insert_date', 'update_date')
    raw_id_fields = ('domain',)
    fieldsets = (
        (None, {
            'fields': (
                'domain_setting_uuid',
                'domain',
                'app_uuid',
                'domain_setting_category',
                'domain_setting_subcategory',
                'domain_setting_name',
                'domain_setting_value',
                'domain_setting_order',
                'domain_setting_enabled',
            ),
        }),
        (_('Description'), {
            'fields': ('domain_setting_description',),
            'classes': ('collapse',),
        }),
        (_('Audit'), {
            'fields': ('insert_date', 'insert_user', 'update_date', 'update_user'),
            'classes': ('collapse',),
        }),
    )


@admin.register(DefaultSetting)
class DefaultSettingAdmin(admin.ModelAdmin):
    list_display = (
        'default_setting_category',
        'default_setting_subcategory',
        'default_setting_name',
        'default_setting_value',
        'default_setting_enabled',
        'default_setting_order',
    )
    list_filter = ('default_setting_enabled', 'default_setting_category')
    search_fields = (
        'default_setting_category',
        'default_setting_subcategory',
        'default_setting_name',
        'default_setting_value',
    )
    ordering = ('default_setting_category', 'default_setting_subcategory', 'default_setting_order')
    readonly_fields = ('default_setting_uuid', 'insert_date', 'update_date')
    fieldsets = (
        (None, {
            'fields': (
                'default_setting_uuid',
                'app_uuid',
                'default_setting_category',
                'default_setting_subcategory',
                'default_setting_name',
                'default_setting_value',
                'default_setting_order',
                'default_setting_enabled',
            ),
        }),
        (_('Description'), {
            'fields': ('default_setting_description',),
            'classes': ('collapse',),
        }),
        (_('Audit'), {
            'fields': ('insert_date', 'insert_user', 'update_date', 'update_user'),
            'classes': ('collapse',),
        }),
    )


@admin.register(Group)
class GroupAdmin(admin.ModelAdmin):
    list_display = (
        'group_name',
        'tenant',
        'domain',
        'group_level',
        'group_protected',
        'insert_date',
    )
    list_filter = ('group_protected', 'group_level', 'tenant', 'domain')
    search_fields = ('group_name', 'group_description', 'tenant__tenant_code', 'domain__domain_name')
    ordering = ('tenant', 'group_name')
    readonly_fields = ('group_uuid', 'insert_date', 'update_date')
    raw_id_fields = ('tenant', 'domain')
    fieldsets = (
        (None, {
            'fields': (
                'group_uuid',
                'tenant',
                'domain',
                'group_name',
                'group_level',
                'group_protected',
            ),
        }),
        (_('Description'), {
            'fields': ('group_description',),
            'classes': ('collapse',),
        }),
        (_('Audit'), {
            'fields': ('insert_date', 'insert_user', 'update_date', 'update_user'),
            'classes': ('collapse',),
        }),
    )


@admin.register(Permission)
class PermissionAdmin(admin.ModelAdmin):
    list_display = ('permission_name', 'permission_description')
    search_fields = ('permission_name', 'permission_description')
    ordering = ('permission_name',)
    readonly_fields = ('permission_uuid',)


@admin.register(GroupPermission)
class GroupPermissionAdmin(admin.ModelAdmin):
    list_display = (
        'group',
        'tenant',
        'domain',
        'permission_name',
        'permission_assigned',
        'insert_date',
    )
    list_filter = ('permission_assigned', 'tenant', 'domain')
    search_fields = ('group__group_name', 'permission_name', 'tenant__tenant_code', 'domain__domain_name')
    ordering = ('group', 'permission_name')
    readonly_fields = ('group_permission_uuid', 'insert_date')
    raw_id_fields = ('tenant', 'domain', 'group')


class UserGroupInline(admin.TabularInline):
    model = UserGroup
    extra = 0
    raw_id_fields = ('group', 'tenant', 'domain')
    readonly_fields = ('user_group_uuid', 'insert_date')


class UserSettingInline(admin.TabularInline):
    model = UserSetting
    extra = 0
    raw_id_fields = ('tenant', 'domain')
    readonly_fields = ('user_setting_uuid', 'insert_date')


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = (
        'username',
        'tenant',
        'domain',
        'user_email',
        'user_enabled',
        'is_staff',
        'is_superuser',
        'insert_date',
    )
    list_filter = ('user_enabled', 'is_staff', 'is_superuser', 'tenant', 'domain')
    search_fields = ('username', 'user_email', 'tenant__tenant_code', 'domain__domain_name')
    ordering = ('tenant', 'username')
    readonly_fields = ('user_uuid', 'insert_date', 'update_date')
    raw_id_fields = ('tenant', 'domain')
    inlines = [UserGroupInline, UserSettingInline]

    fieldsets = (
        (None, {
            'fields': ('user_uuid', 'tenant', 'domain', 'username', 'password'),
        }),
        (_('Personal info'), {
            'fields': ('user_email', 'user_status', 'user_totp_secret', 'api_key'),
        }),
        (_('Permissions'), {
            'fields': ('user_enabled', 'is_staff', 'is_superuser'),
        }),
        (_('Audit'), {
            'fields': ('insert_date', 'insert_user', 'update_date', 'update_user'),
            'classes': ('collapse',),
        }),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('tenant', 'domain', 'username', 'password1', 'password2'),
        }),
    )

    filter_horizontal = ()


@admin.register(UserGroup)
class UserGroupAdmin(admin.ModelAdmin):
    list_display = ('user', 'group', 'tenant', 'domain', 'insert_date')
    list_filter = ('tenant', 'domain')
    search_fields = ('user__username', 'group__group_name', 'tenant__tenant_code', 'domain__domain_name')
    ordering = ('user', 'group')
    readonly_fields = ('user_group_uuid', 'insert_date')
    raw_id_fields = ('user', 'group', 'tenant', 'domain')


@admin.register(UserSetting)
class UserSettingAdmin(admin.ModelAdmin):
    list_display = (
        'user',
        'tenant',
        'domain',
        'user_setting_category',
        'user_setting_subcategory',
        'user_setting_name',
        'user_setting_value',
        'user_setting_enabled',
    )
    list_filter = ('user_setting_enabled', 'user_setting_category', 'tenant', 'domain')
    search_fields = (
        'user__username',
        'user_setting_category',
        'user_setting_subcategory',
        'user_setting_name',
        'user_setting_value',
    )
    ordering = ('user', 'user_setting_category', 'user_setting_subcategory', 'user_setting_order')
    readonly_fields = ('user_setting_uuid', 'insert_date')
    raw_id_fields = ('user', 'tenant', 'domain')


@admin.register(UserLog)
class UserLogAdmin(admin.ModelAdmin):
    list_display = (
        'username',
        'user_log_type',
        'tenant',
        'domain',
        'user_log_ipv4',
        'user_log_timestamp',
    )
    list_filter = ('user_log_type', 'tenant', 'domain')
    search_fields = ('username', 'user_log_ipv4', 'user_log_message', 'tenant__tenant_code', 'domain__domain_name')
    ordering = ('-user_log_timestamp',)
    readonly_fields = ('user_log_uuid', 'user_log_timestamp')
    raw_id_fields = ('user', 'tenant', 'domain')
    date_hierarchy = 'user_log_timestamp'

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(DomainLimit)
class DomainLimitAdmin(admin.ModelAdmin):
    list_display = (
        'domain',
        'tenant',
        'domain_limit_name',
        'domain_limit_value',
        'domain_limit_enabled',
    )
    list_filter = ('domain_limit_enabled', 'tenant', 'domain')
    search_fields = ('domain__domain_name', 'tenant__tenant_code', 'domain_limit_name', 'domain_limit_value')
    ordering = ('domain', 'domain_limit_name')
    readonly_fields = ('domain_limit_uuid',)
    raw_id_fields = ('tenant', 'domain')
