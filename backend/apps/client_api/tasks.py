"""
Celery tasks for webhook delivery with retry logic.
"""
import hashlib
import hmac
import json
import logging
from datetime import datetime, timezone

import requests
from celery import shared_task
from django.utils import timezone as dj_timezone

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 3
RETRY_DELAY = 30  # seconds


def _build_payload(event, tenant_code, tenant_id, object_id, data=None):
    payload = {
        'event': event,
        'tenant_code': tenant_code,
        'tenant_id': str(tenant_id),
        'object_id': str(object_id),
        'timestamp': dj_timezone.now().isoformat(),
    }
    if data:
        payload.update(data)
    return payload


@shared_task(bind=True, name='client_api.fire_webhook_event')
def fire_webhook_event(self, tenant_id, event, object_id, inline_data=None):
    """
    Fire a webhook event to all active API keys for the given tenant
    that have a webhook_url configured.
    """
    from apps.client_api.models import TenantAPIKey, WebhookDelivery
    from core.models import Tenant

    try:
        tenant = Tenant.objects.get(tenant_uuid=tenant_id)
    except Tenant.DoesNotExist:
        logger.warning('fire_webhook_event: tenant %s not found', tenant_id)
        return

    # For api_key.created/updated/deleted, only deliver to the affected key itself
    # to avoid fan-out to all other keys for that tenant.
    if event.startswith('api_key.') and object_id:
        keys = TenantAPIKey.objects.filter(id=object_id, is_active=True, webhook_url__gt='')
    else:
        keys = TenantAPIKey.objects.filter(tenant=tenant, is_active=True, webhook_url__gt='')
    if not keys.exists():
        return

    payload = _build_payload(event, tenant.tenant_code, tenant.tenant_uuid, object_id, inline_data)
    payload_bytes = json.dumps(payload, default=str).encode('utf-8')

    for api_key in keys:
        delivery = WebhookDelivery.objects.create(
            api_key=api_key,
            event=event,
            payload=payload,
        )
        _deliver_webhook.delay(str(delivery.id))


@shared_task(bind=True, name='client_api.deliver_webhook', max_retries=MAX_ATTEMPTS - 1)
def _deliver_webhook(self, delivery_id):
    from apps.client_api.models import WebhookDelivery

    try:
        delivery = WebhookDelivery.objects.select_related('api_key').get(id=delivery_id)
    except WebhookDelivery.DoesNotExist:
        return

    api_key = delivery.api_key
    if not api_key.is_active or not api_key.webhook_url:
        delivery.status = WebhookDelivery.STATUS_FAILED
        delivery.last_error = 'API key inactive or no webhook_url.'
        delivery.save(update_fields=['status', 'last_error'])
        return

    payload_bytes = json.dumps(delivery.payload, default=str).encode('utf-8')

    headers = {
        'Content-Type': 'application/json',
        'User-Agent': 'IHSPBX-Webhook/1.0',
    }
    if api_key.webhook_secret:
        sig = hmac.new(
            api_key.webhook_secret.encode(),
            payload_bytes,
            hashlib.sha256,
        ).hexdigest()
        headers['X-Signature'] = sig

    delivery.attempts += 1
    logger.info(
        'Webhook delivery %s attempt %d: event=%s url=%s',
        delivery_id, delivery.attempts, delivery.event, api_key.webhook_url,
    )
    try:
        resp = requests.post(
            api_key.webhook_url,
            data=payload_bytes,
            headers=headers,
            timeout=10,
        )
        delivery.last_response_code = resp.status_code
        if resp.status_code < 300:
            delivery.status = WebhookDelivery.STATUS_SUCCESS
            delivery.delivered_at = dj_timezone.now()
            delivery.save(update_fields=['status', 'attempts', 'last_response_code', 'delivered_at'])
            logger.info(
                'Webhook delivery %s succeeded: event=%s url=%s status=%d',
                delivery_id, delivery.event, api_key.webhook_url, resp.status_code,
            )
            return
        else:
            delivery.last_error = f'HTTP {resp.status_code}'
            logger.warning(
                'Webhook delivery %s failed: event=%s url=%s status=%d',
                delivery_id, delivery.event, api_key.webhook_url, resp.status_code,
            )
    except requests.RequestException as exc:
        delivery.last_error = str(exc)
        delivery.last_response_code = None
        logger.warning(
            'Webhook delivery %s error: event=%s url=%s error=%s',
            delivery_id, delivery.event, api_key.webhook_url, exc,
        )

    delivery.save(update_fields=['status', 'attempts', 'last_response_code', 'last_error'])

    if delivery.attempts < MAX_ATTEMPTS:
        raise self.retry(countdown=RETRY_DELAY)
    else:
        delivery.status = WebhookDelivery.STATUS_FAILED
        delivery.save(update_fields=['status'])
        logger.error(
            'Webhook delivery %s failed after %d attempts for event %s',
            delivery_id, delivery.attempts, delivery.event,
        )
