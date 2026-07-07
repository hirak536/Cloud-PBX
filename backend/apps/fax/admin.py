from django.contrib import admin, messages
from django.utils.html import format_html
from .models import Fax, FaxFile, FaxFtpDelivery


class FaxFileInline(admin.TabularInline):
    model = FaxFile
    extra = 0
    readonly_fields = ['fax_file_uuid', 'fax_file_status', 'fax_file_pages',
                       'fax_file_caller_id_number', 'fax_file_destination_number',
                       'fax_file_date', 'insert_date']
    fields = ['fax_file_status', 'fax_file_name', 'fax_file_pages',
              'fax_file_caller_id_number', 'fax_file_destination_number',
              'fax_file_date', 'fax_file_path']


@admin.register(Fax)
class FaxAdmin(admin.ModelAdmin):
    list_display = ['fax_name', 'fax_extension', 'fax_email', 'fax_caller_id_number', 'fax_enabled']
    list_filter = ['fax_enabled', 'domain']
    search_fields = ['fax_name', 'fax_extension', 'fax_email']
    readonly_fields = ['fax_uuid', 'insert_date', 'update_date']
    inlines = [FaxFileInline]
    fieldsets = [
        ('Identity', {
            'fields': ['fax_uuid', 'tenant', 'domain', 'fax_name', 'fax_extension', 'fax_enabled'],
        }),
        ('Caller ID', {
            'fields': ['fax_caller_id_name', 'fax_caller_id_number'],
        }),
        ('Delivery', {
            'fields': ['fax_delivery_mode'],
            'description': 'How received faxes are delivered: emailed, uploaded to FTP, or both.',
        }),
        ('Email Delivery', {
            'fields': ['fax_email', 'fax_email_connection'],
            'description': 'Received faxes can be emailed to this address.',
        }),
        ('FTP Delivery', {
            'fields': ['fax_ftp_host', 'fax_ftp_port', 'fax_ftp_use_tls',
                       'fax_ftp_username', 'fax_ftp_password', 'fax_ftp_path'],
            'description': 'Received faxes can be uploaded to this FTP/FTPS server.',
            'classes': ['collapse'],
        }),
        ('Routing', {
            'fields': ['fax_forward_number', 'fax_toll_allow', 'fax_accountcode'],
            'classes': ['collapse'],
        }),
        ('Audit', {
            'fields': ['insert_date', 'update_date'],
            'classes': ['collapse'],
        }),
    ]


@admin.register(FaxFile)
class FaxFileAdmin(admin.ModelAdmin):
    list_display = [
        'fax', 'fax_file_status', 'fax_file_name', 'fax_file_pages',
        'fax_file_caller_id_number', 'fax_file_destination_number', 'fax_file_date',
    ]
    list_filter = ['fax_file_status', 'fax_file_type', 'domain']
    search_fields = ['fax_file_name', 'fax_file_caller_id_number', 'fax_file_destination_number']
    readonly_fields = ['fax_file_uuid', 'insert_date', 'fax_file_path']
    ordering = ['-fax_file_date']


@admin.register(FaxFtpDelivery)
class FaxFtpDeliveryAdmin(admin.ModelAdmin):
    """Audit log of inbound-fax FTP uploads. Mirrors WebhookDeliveryAdmin."""
    list_display = ['created_at', 'fax', 'remote_name', 'target', 'status_badge',
                    'attempts', 'last_error_short', 'delivered_at']
    list_filter = ['status', 'use_tls', 'tenant']
    search_fields = ['remote_name', 'host', 'username', 'last_error',
                     'fax__fax_name', 'fax__fax_extension']
    ordering = ['-created_at']
    readonly_fields = ['id', 'fax', 'fax_file', 'tenant', 'host', 'port', 'username',
                       'remote_path', 'remote_name', 'use_tls', 'file_size_bytes',
                       'status', 'attempts', 'last_response', 'last_error',
                       'created_at', 'delivered_at']
    actions = ['retry_delivery']

    def target(self, obj):
        scheme = 'ftps' if obj.use_tls else 'ftp'
        return f'{scheme}://{obj.host}:{obj.port}{obj.remote_path}'
    target.short_description = 'Target'

    def status_badge(self, obj):
        colors = {'success': 'green', 'failed': 'red', 'pending': 'orange'}
        color = colors.get(obj.status, 'gray')
        return format_html('<span style="color:{}; font-weight:bold;">{}</span>',
                           color, obj.status.upper())
    status_badge.short_description = 'Status'

    def last_error_short(self, obj):
        if not obj.last_error:
            return ''
        return obj.last_error[:80] + ('…' if len(obj.last_error) > 80 else '')
    last_error_short.short_description = 'Last Error'

    @admin.action(description='Retry selected FTP deliveries')
    def retry_delivery(self, request, queryset):
        from .tasks import upload_fax_to_ftp
        count = 0
        for delivery in queryset:
            if not delivery.fax_file_id:
                continue
            upload_fax_to_ftp.delay(str(delivery.fax_file_id))
            count += 1
        self.message_user(request, f'{count} fax FTP upload(s) queued for retry.', messages.SUCCESS)
