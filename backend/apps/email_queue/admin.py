from django.contrib import admin
from .models import EmailQueue, EmailDelivery

@admin.register(EmailQueue)
class EmailQueueAdmin(admin.ModelAdmin):
    list_display = ['email_queue_to', 'email_queue_subject', 'email_queue_status', 'insert_date']
    list_filter = ['email_queue_status']
    search_fields = ['email_queue_to', 'email_queue_subject']


@admin.register(EmailDelivery)
class EmailDeliveryAdmin(admin.ModelAdmin):
    list_display = ['created_at', 'category', 'email_to', 'subject', 'status', 'attachment_count']
    list_filter = ['status', 'category', 'created_at']
    search_fields = ['email_to', 'subject', 'related_uuid']
    date_hierarchy = 'created_at'
    # An audit trail is worthless if it can be edited after the fact.
    readonly_fields = [f.name for f in EmailDelivery._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
