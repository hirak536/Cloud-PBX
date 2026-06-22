from django.contrib import admin
from .models import Fax, FaxFile


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
