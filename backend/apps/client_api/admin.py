from django.contrib import admin, messages
from django.utils.html import format_html
from .models import MasterAPIKey, TenantAPIKey, WebhookDelivery


@admin.register(TenantAPIKey)
class TenantAPIKeyAdmin(admin.ModelAdmin):
    list_display = ['label', 'tenant', 'is_active', 'created_at', 'expires_at', 'webhook_url']
    list_filter = ['is_active', 'tenant']
    search_fields = ['label', 'tenant__tenant_code', 'tenant__tenant_name']
    readonly_fields = ['id', 'key_hash', 'created_at', 'created_by']
    fields = ['id', 'tenant', 'label', 'created_by', 'created_at', 'expires_at', 'is_active', 'webhook_url', 'webhook_secret', 'key_hash']


@admin.register(MasterAPIKey)
class MasterAPIKeyAdmin(admin.ModelAdmin):
    list_display = ['label', 'is_active', 'created_at', 'created_by']
    readonly_fields = ['id', 'key_hash', 'created_at', 'created_by']
    fields = ['id', 'label', 'created_by', 'created_at', 'is_active', 'key_hash']

    def save_model(self, request, obj, form, change):
        if not change:
            # New key — generate and show plaintext once
            instance, plaintext = MasterAPIKey.generate(label=obj.label, created_by=request.user)
            self.message_user(request, f'Master API Key (copy now, shown once): {plaintext}')
            return  # already saved by generate()
        super().save_model(request, obj, form, change)


@admin.register(WebhookDelivery)
class WebhookDeliveryAdmin(admin.ModelAdmin):
    list_display = ['created_at', 'event', 'api_key', 'status_badge', 'attempts', 'last_response_code', 'last_error_short', 'delivered_at']
    list_filter = ['status', 'event', 'api_key__tenant']
    search_fields = ['event', 'api_key__label', 'api_key__tenant__tenant_code', 'last_error']
    ordering = ['-created_at']
    readonly_fields = ['id', 'api_key', 'url', 'event', 'payload', 'status', 'attempts', 'last_response_code', 'last_error', 'created_at', 'delivered_at']
    actions = ['retry_delivery']

    def status_badge(self, obj):
        colors = {
            'success': 'green',
            'failed': 'red',
            'pending': 'orange',
        }
        color = colors.get(obj.status, 'gray')
        return format_html('<span style="color:{}; font-weight:bold;">{}</span>', color, obj.status.upper())
    status_badge.short_description = 'Status'

    def last_error_short(self, obj):
        if not obj.last_error:
            return ''
        return obj.last_error[:80] + ('…' if len(obj.last_error) > 80 else '')
    last_error_short.short_description = 'Last Error'

    @admin.action(description='Retry selected webhook deliveries')
    def retry_delivery(self, request, queryset):
        from .tasks import _deliver_webhook
        count = 0
        for delivery in queryset:
            delivery.attempts = 0
            delivery.status = WebhookDelivery.STATUS_PENDING
            delivery.save(update_fields=['attempts', 'status'])
            _deliver_webhook.delay(str(delivery.id))
            count += 1
        self.message_user(request, f'{count} webhook(s) queued for retry.', messages.SUCCESS)
