from django.core.mail import get_connection, EmailMessage
from django.core.management.base import BaseCommand
from django.conf import settings
from django.utils import timezone
from apps.email_queue.models import EmailQueue
from apps.email_queue.logging_utils import send_and_log
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Send all pending emails in the queue via SMTP'

    def handle(self, *args, **kwargs):
        pending = EmailQueue.objects.filter(email_queue_status='pending')
        count = pending.count()

        if count == 0:
            self.stdout.write('No pending emails.')
            return

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
                    msg = EmailMessage(
                        subject=item.email_queue_subject,
                        body=item.email_queue_body,
                        from_email=item.email_queue_from,
                        to=[item.email_queue_to],
                        cc=[c.strip() for c in item.email_queue_cc.split(',') if c.strip()],
                        connection=connection,
                    )
                    send_and_log(msg, category='queue', related_uuid=str(item.pk),
                                 tenant=item.tenant)
                    item.email_queue_status = 'sent'
                    item.email_queue_date = timezone.now()
                    item.save(update_fields=['email_queue_status', 'email_queue_date'])
                    sent += 1
                except Exception as e:
                    logger.exception('Failed to send email %s', item.pk)
                    item.email_queue_status = 'failed'
                    item.email_queue_retry_count += 1
                    item.save(update_fields=['email_queue_status', 'email_queue_retry_count'])
                    failed += 1
        finally:
            connection.close()

        self.stdout.write(f'Sent: {sent}, Failed: {failed}')
