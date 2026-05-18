"""
DatabaseEmailBackend

Saves outgoing emails to the v_email_queue table instead of sending via SMTP.
A separate process (cron, celery, or management command) can then deliver them.

Usage in .env:
    EMAIL_BACKEND=apps.common.email_backend.DatabaseEmailBackend
"""

from django.core.mail.backends.base import BaseEmailBackend
from django.utils import timezone


class DatabaseEmailBackend(BaseEmailBackend):
    def send_messages(self, email_messages):
        from apps.email_queue.models import EmailQueue

        sent = 0
        for msg in email_messages:
            try:
                to_list = msg.to or []
                # Extract HTML alternative if present
                html_body = ''
                for content, mimetype in getattr(msg, 'alternatives', []):
                    if mimetype == 'text/html':
                        html_body = content
                        break
                for recipient in to_list:
                    EmailQueue.objects.create(
                        email_queue_from=msg.from_email or '',
                        email_queue_to=recipient,
                        email_queue_cc=', '.join(msg.cc or []),
                        email_queue_subject=msg.subject or '',
                        email_queue_body=html_body or msg.body or '',
                        email_queue_status='pending',
                        email_queue_date=timezone.now(),
                    )
                # Trigger immediate delivery via Celery
                try:
                    from apps.email_queue.tasks import send_pending_emails
                    send_pending_emails.delay()
                except Exception:
                    pass  # Beat will pick it up within 1 minute if Celery unavailable
                sent += 1
            except Exception:
                if not self.fail_silently:
                    raise
        return sent
