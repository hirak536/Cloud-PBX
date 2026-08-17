"""Helpers for recording outbound email into EmailDelivery.

send_and_log() wraps a message's .send() so the attempt is recorded whether it
succeeds or raises. Callers keep their existing retry behaviour: the original
exception is re-raised after logging.
"""

import logging
import re

logger = logging.getLogger(__name__)

# Temporary passwords are mailed in the body by the account flows in core.views.
# Storing them would put live credentials in a table that is exposed over the
# tenant-scoped REST API, so they are masked before the row is written.
_SECRET_PATTERNS = [
    re.compile(r'((?:temporary |temp )?password\s*(?:is)?\s*[:=]\s*)(\S+)', re.IGNORECASE),
    re.compile(r'(<td[^>]*>\s*)([^<\s]{8,})(\s*</td>\s*<!--\s*password\s*-->)', re.IGNORECASE),
]

_REDACTED = '[redacted]'


def scrub_secrets(text):
    """Mask credential-looking values in an email body."""
    if not text:
        return ''
    for pattern in _SECRET_PATTERNS:
        if pattern.groups >= 3:
            text = pattern.sub(lambda m: m.group(1) + _REDACTED + m.group(3), text)
        else:
            text = pattern.sub(lambda m: m.group(1) + _REDACTED, text)
    return text


# Bodies are for diagnosis, not archival; cap them so a large HTML mail cannot
# bloat a row.
_MAX_BODY = 20000


def log_email_attempt(message, *, category='other', related_uuid='', tenant=None,
                      status='sent', error=''):
    """Write one EmailDelivery row describing a send attempt.

    Never raises — logging must not be able to break an email that otherwise
    delivered fine.
    """
    from .delivery_log import EmailDelivery  # noqa: PLC0415

    try:
        attachments = list(getattr(message, 'attachments', []) or [])
        names = []
        total_bytes = 0
        for att in attachments:
            # Django attachments are (filename, content, mimetype) tuples, but
            # a raw MIMEBase object is also legal and has no such shape.
            if isinstance(att, (tuple, list)) and att:
                names.append(str(att[0]))
                if len(att) > 1 and isinstance(att[1], (bytes, bytearray, str)):
                    total_bytes += len(att[1])
            else:
                names.append(getattr(att, 'get_filename', lambda: 'attachment')() or 'attachment')

        body = scrub_secrets(getattr(message, 'body', '') or '')

        EmailDelivery.objects.create(
            tenant=tenant,
            category=category,
            related_uuid=str(related_uuid or ''),
            email_from=getattr(message, 'from_email', '') or '',
            email_to=', '.join(getattr(message, 'to', []) or []),
            email_cc=', '.join(getattr(message, 'cc', []) or []),
            subject=(getattr(message, 'subject', '') or '')[:512],
            body=body[:_MAX_BODY],
            attachment_names=', '.join(names)[:2000],
            attachment_count=len(attachments),
            attachment_bytes=total_bytes,
            status=status,
            error=str(error or '')[:5000],
        )
    except Exception:
        logger.exception('log_email_attempt: failed to record email delivery')


def send_and_log(message, *, category='other', related_uuid='', tenant=None,
                 fail_silently=False):
    """Send `message`, recording the outcome either way.

    Returns whatever message.send() returns. Re-raises on failure so existing
    Celery retry logic is unchanged.
    """
    try:
        result = message.send(fail_silently=fail_silently)
    except Exception as exc:
        log_email_attempt(message, category=category, related_uuid=related_uuid,
                          tenant=tenant, status='failed', error=exc)
        raise
    log_email_attempt(message, category=category, related_uuid=related_uuid,
                      tenant=tenant, status='sent')
    return result
