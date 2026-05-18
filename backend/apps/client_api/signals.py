"""
Django signals that fire webhook events when Extensions or Destinations change.
"""
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from apps.client_api.models import TenantAPIKey
from apps.destinations.models import Destination
from apps.extensions.models import Extension


def _fire(event, tenant_id, object_id, inline_data=None):
    from .tasks import fire_webhook_event
    fire_webhook_event.delay(str(tenant_id), event, str(object_id), inline_data)


@receiver(post_save, sender=Extension)
def extension_saved(sender, instance, created, **kwargs):
    if not instance.tenant_id:
        return
    event = 'extension.created' if created else 'extension.updated'
    inline_data = None
    if created:
        inline_data = {
            'phone': instance.extension,
            'sip_username': instance.sip_username,
            'password': instance.password,
        }
    _fire(event, instance.tenant_id, instance.extension_uuid, inline_data)


@receiver(post_delete, sender=Extension)
def extension_deleted(sender, instance, **kwargs):
    if not instance.tenant_id:
        return
    _fire('extension.deleted', instance.tenant_id, instance.extension_uuid)


@receiver(post_save, sender=Destination)
def destination_saved(sender, instance, created, **kwargs):
    if not instance.tenant_id:
        return
    event = 'did.created' if created else 'did.updated'
    _fire(event, instance.tenant_id, instance.destination_uuid)


@receiver(post_delete, sender=Destination)
def destination_deleted(sender, instance, **kwargs):
    if not instance.tenant_id:
        return
    _fire('did.deleted', instance.tenant_id, instance.destination_uuid)


@receiver(post_save, sender=TenantAPIKey)
def api_key_saved(sender, instance, created, **kwargs):
    if not instance.tenant_id:
        return
    event = 'api_key.created' if created else 'api_key.updated'
    inline_data = {
        'tenant_name': instance.tenant.tenant_name if instance.tenant_id else None,
        'label': instance.label,
    }
    if created:
        # Plaintext is attached by generate() for one-time inclusion in the webhook payload
        plaintext = getattr(instance, '_plaintext', None)
        if plaintext:
            inline_data['api_key'] = plaintext
    _fire(event, instance.tenant_id, instance.id, inline_data=inline_data)


@receiver(post_delete, sender=TenantAPIKey)
def api_key_deleted(sender, instance, **kwargs):
    if not instance.tenant_id:
        return
    _fire('api_key.deleted', instance.tenant_id, instance.id)
