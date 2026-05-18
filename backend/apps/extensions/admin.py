from django.contrib import admin
from .models import Extension, ExtensionUser


class ExtensionUserInline(admin.TabularInline):
    model = ExtensionUser
    extra = 0


@admin.register(Extension)
class ExtensionAdmin(admin.ModelAdmin):
    list_display = [
        'sip_username', 'extension', 'tenant',
        'effective_caller_id_name', 'call_forward_active', 'voicemail_enabled', 'enabled',
    ]
    list_filter = ['enabled', 'voicemail_enabled', 'call_forward_active', 'tenant']
    search_fields = ['extension', 'sip_username', 'number_alias', 'effective_caller_id_name']
    readonly_fields = ['sip_username', 'domain', 'insert_date', 'update_date']
    inlines = [ExtensionUserInline]
    fieldsets = [
        ('Identity', {
            'fields': ['tenant', 'extension', 'sip_username', 'number_alias', 'password'],
        }),
        ('Caller ID', {
            'fields': [
                'effective_caller_id_name', 'effective_caller_id_number',
                'emergency_caller_id_name', 'emergency_caller_id_number',
                'directory_full_name', 'directory_visible', 'directory_exten_visible',
            ],
        }),
        ('Call Settings', {
            'fields': [
                'user_context', 'toll_allow', 'accountcode',
                'call_timeout', 'call_group', 'call_screen_enabled',
                'limit_max', 'limit_destination', 'hold_music',
                'user_record', 'max_registrations', 'force_ping',
            ],
        }),
        ('Codec & Media', {
            'fields': ['codec_preference', 'absolute_codec_string', 'sip_bypass_media'],
            'description': (
                'Built-in: PCMU, PCMA, speex, VP8, VP9. '
                'mod_spandsp: G722, G726-32, GSM, ADPCM. '
                'mod_opus: OPUS. mod_g729: G729 (license). '
                'mod_av: H263, H264. '
                'Enter comma-separated codec names, e.g. PCMU,PCMA,G722'
            ),
        }),
        ('Additional Destinations', {
            'fields': [
                'call_forward_active',
                'forward_all_enabled', 'forward_all_destination',
                'forward_no_answer_enabled', 'forward_no_answer_destination',
                'forward_busy_enabled', 'forward_busy_destination',
                'forward_user_not_registered_enabled', 'forward_user_not_registered_destination',
                'forward_on_condition_enabled', 'forward_on_condition', 'forward_on_condition_destination',
            ],
            'description': 'All rules only apply when "Additional Destinations Active" is checked.',
        }),
        ('Voicemail', {
            'fields': [
                'voicemail_enabled', 'voicemail_id', 'voicemail_password',
                'voicemail_mail_to', 'voicemail_file', 'voicemail_local_after_email',
                'mwi_account',
            ],
        }),
        ('Outbound', {
            'fields': [
                'outbound_route',
                'outbound_xheader_name',
                'outbound_xheader_value',
                'outbound_caller_id_name',
                'outbound_caller_id_number',
            ],
            'description': (
                'Default outbound route: the SIP trunk used when this extension dials out. '
                'Custom X-header: a SIP header sent on every outbound call '
                '(e.g. X-Tenant-ID / ACM-Corp). Used by carriers for tenant tracking.'
            ),
        }),
        ('Advanced SIP', {
            'classes': ['collapse'],
            'fields': [
                'auth_acl', 'cidr', 'sip_force_contact', 'sip_force_expires',
                'language',
            ],
        }),
        ('Audit', {
            'classes': ['collapse'],
            'fields': ['domain', 'enabled', 'description', 'insert_date', 'insert_user', 'update_date', 'update_user'],
        }),
    ]


@admin.register(ExtensionUser)
class ExtensionUserAdmin(admin.ModelAdmin):
    list_display = ['extension', 'user']
    list_filter = []
    search_fields = ['extension__extension', 'user__username']
