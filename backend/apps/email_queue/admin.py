from django.contrib import admin
from .models import EmailQueue

@admin.register(EmailQueue)
class EmailQueueAdmin(admin.ModelAdmin):
    list_display = ['email_queue_to', 'email_queue_subject', 'email_queue_status', 'insert_date']
    list_filter = ['email_queue_status']
    search_fields = ['email_queue_to', 'email_queue_subject']
