import logging
from celery import shared_task
from django.core.mail import get_connection, EmailMultiAlternatives
from django.conf import settings
from django.utils import timezone

from .logging_utils import send_and_log

logger = logging.getLogger(__name__)


@shared_task(name='email_queue.purge_delivery_log')
def purge_delivery_log(days: int = 60):
    """Prune EmailDelivery rows older than ``days`` days (60-day retention).

    Deleted in batches: voicemail and fax notifications make this the busiest
    table in the app, and a single unbounded DELETE would hold locks long enough
    to stall concurrent sends.
    """
    from datetime import timedelta  # noqa: PLC0415
    from django.utils import timezone  # noqa: PLC0415
    from .delivery_log import EmailDelivery  # noqa: PLC0415

    cutoff = timezone.now() - timedelta(days=days)
    total = 0
    while True:
        batch = list(
            EmailDelivery.objects.filter(created_at__lt=cutoff)
            .values_list('pk', flat=True)[:1000]
        )
        if not batch:
            break
        deleted, _ = EmailDelivery.objects.filter(pk__in=batch).delete()
        total += deleted
        if deleted == 0:  # guard against a non-shrinking queryset
            break

    if total:
        logger.info('purge_delivery_log: deleted %d rows older than %d days', total, days)
    return total


@shared_task(name='email_queue.send_pending')
def send_pending_emails():
    from .models import EmailQueue

    pending = EmailQueue.objects.filter(email_queue_status='pending')
    count = pending.count()
    if count == 0:
        return {'sent': 0, 'failed': 0}

    connection = get_connection(
        backend='django.core.mail.backends.smtp.EmailBackend',
        host=settings.EMAIL_HOST,
        port=settings.EMAIL_PORT,
        username=settings.EMAIL_HOST_USER,
        password=settings.EMAIL_HOST_PASSWORD,
        use_tls=settings.EMAIL_USE_TLS,
        use_ssl=settings.EMAIL_USE_SSL,
        fail_silently=False,
    )

    sent = failed = 0
    try:
        connection.open()
        for item in pending:
            try:
                body = item.email_queue_body or ''
                is_html = body.strip().startswith('<')
                msg = EmailMultiAlternatives(
                    subject=item.email_queue_subject,
                    body='Please view this email in an HTML-compatible email client.' if is_html else body,
                    from_email=item.email_queue_from,
                    to=[item.email_queue_to],
                    cc=[c.strip() for c in item.email_queue_cc.split(',') if c.strip()],
                    connection=connection,
                )
                if is_html:
                    msg.attach_alternative(body, 'text/html')
                send_and_log(msg, category='queue', related_uuid=str(item.pk),
                             tenant=item.tenant)
                item.email_queue_status = 'sent'
                item.email_queue_date = timezone.now()
                item.save(update_fields=['email_queue_status', 'email_queue_date'])
                sent += 1
            except Exception:
                logger.exception('Failed to send email %s', item.pk)
                item.email_queue_status = 'failed'
                item.email_queue_retry_count += 1
                item.save(update_fields=['email_queue_status', 'email_queue_retry_count'])
                failed += 1
    finally:
        connection.close()

    logger.info('Email queue: sent=%d failed=%d', sent, failed)
    return {'sent': sent, 'failed': failed}
