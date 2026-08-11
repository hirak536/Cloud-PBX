"""
Celery tasks for fax status tracking.
"""
import logging
import os
import re
import time

from celery import shared_task
from django.db import models
from django.conf import settings

logger = logging.getLogger(__name__)

# How long to wait between polls (seconds), and how many attempts before giving up
_POLL_INTERVAL = 10
_MAX_ATTEMPTS = 60  # 10 min total


@shared_task(bind=True, max_retries=_MAX_ATTEMPTS, default_retry_delay=_POLL_INTERVAL, acks_late=True)
def poll_fax_result(self, fax_file_uuid: str, channel_uuid: str):
    """
    Poll FreeSWITCH until the outbound txfax channel is gone, then read
    fax result variables and update the FaxFile status to 'sent' or 'failed'.

    Scheduled immediately after a successful originate (+OK <uuid>).
    Retries every _POLL_INTERVAL seconds for up to _MAX_ATTEMPTS attempts.
    """
    from esl.client import get_esl_client
    from apps.fax.models import FaxFile

    from django.db import transaction
    
    with transaction.atomic():
        try:
            ff = FaxFile.objects.select_for_update().get(fax_file_uuid=fax_file_uuid)
        except FaxFile.DoesNotExist:
            logger.warning(f'poll_fax_result: FaxFile {fax_file_uuid} not found, aborting')
            return

        # If already resolved (could happen on duplicate task or retry), bail out
        if ff.fax_file_status not in ('pending',):
            logger.info(f'poll_fax_result: FaxFile {fax_file_uuid} already {ff.fax_file_status} — skipping')
            return

    try:
        esl = get_esl_client()

        # Check if channel still exists
        channel_exists_raw = esl.api(f'uuid_exists {channel_uuid}')
        channel_exists = channel_exists_raw.strip().lower() == 'true'

        attempt = self.request.retries + 1
        elapsed_s = attempt * _POLL_INTERVAL

        if channel_exists:
            # Channel still up — increment retry count and retry later
            FaxFile.objects.filter(fax_file_uuid=fax_file_uuid).update(
                retry_count=models.F('retry_count') + 1
            )
            logger.debug(
                f'poll_fax_result: channel still active — uuid={channel_uuid} '
                f'attempt={attempt}/{_MAX_ATTEMPTS} elapsed={elapsed_s}s'
            )
            raise self.retry()

        logger.info(
            f'poll_fax_result: channel gone — uuid={channel_uuid} '
            f'after attempt={attempt} elapsed={elapsed_s}s — reading fax variables'
        )

        # Channel is gone — read fax result variables from the channel's stored variables.
        # FreeSWITCH exposes these via uuid_getvar even after hangup for a short window,
        # but more reliably via the show channels / xml_cdr. We use uuid_getvar with
        # a best-effort approach; if empty we fall back to checking fax_success.
        def getvar(var):
            try:
                raw = esl.api(f'uuid_getvar {channel_uuid} {var}').strip()
                return raw
            except Exception as e:
                logger.debug(f'poll_fax_result: getvar({var!r}) exception: {e}')
                return ''

        fax_success = getvar('fax_success')
        fax_result_code = getvar('fax_result_code')
        fax_result_text = getvar('fax_result_text')
        fax_document_transferred_pages = getvar('fax_document_transferred_pages')
        fax_document_total_pages = getvar('fax_document_total_pages')
        fax_transfer_rate = getvar('fax_transfer_rate')
        fax_t38_negotiated = getvar('fax_t38_negotiated')
        fax_ecm_used = getvar('fax_ecm_used')
        fax_local_station_id = getvar('fax_local_station_id')
        fax_remote_station_id = getvar('fax_remote_station_id')
        fax_remote_id = getvar('fax_remote_id')
        fax_header = getvar('fax_header')
        sip_hangup_cause = getvar('sip_hangup_cause')
        hangup_cause = getvar('hangup_cause')

        logger.info(
            f'poll_fax_result: results — uuid={channel_uuid} '
            f'success={fax_success!r} code={fax_result_code!r} text={fax_result_text!r} '
            f'pages_sent={fax_document_transferred_pages!r}/{fax_document_total_pages!r} '
            f'rate={fax_transfer_rate!r}bps t38_negotiated={fax_t38_negotiated!r} '
            f'ecm={fax_ecm_used!r} remote_id={fax_remote_station_id!r} '
            f'hangup_cause={hangup_cause!r} sip_hangup_cause={sip_hangup_cause!r}'
        )

        if fax_success not in ('1', '0', '') and fax_success.startswith('-ERR'):
            logger.warning(
                f'poll_fax_result: variables unavailable after hangup (channel already expired) '
                f'— uuid={channel_uuid} raw_fax_success={fax_success!r}'
            )

        # fax_success == '1' means all pages transferred successfully.
        # '-ERR No such channel!' means variables are unavailable after hangup —
        # the fax completed (we confirmed channel is gone) so mark as sent optimistically.
        if fax_success == '1':
            new_status = 'sent'
        elif fax_success in ('', '0') and not fax_success.startswith('-ERR'):
            new_status = 'failed'
            logger.warning(
                f'poll_fax_result: fax FAILED — uuid={channel_uuid} '
                f'result_code={fax_result_code!r} result_text={fax_result_text!r} '
                f't38_negotiated={fax_t38_negotiated!r} rate={fax_transfer_rate!r}bps '
                f'hangup_cause={hangup_cause!r} '
                f'(if result_text contains "T.38" or rate is 0, likely a bandwidth/codec issue; '
                f'if hangup_cause is NORMAL_CLEARING with 0 pages, carrier may have rejected T.38)'
            )
        else:
            # Channel gone and variables unavailable — optimistically mark sent
            new_status = 'sent'
            logger.warning(
                f'poll_fax_result: variables expired — marking sent optimistically '
                f'uuid={channel_uuid} raw_fax_success={fax_success!r}'
            )

        update_fields = ['fax_file_status']
        ff.fax_file_status = new_status

        pages = int(fax_document_transferred_pages) if fax_document_transferred_pages.isdigit() and not fax_document_transferred_pages.startswith('-') else None
        if pages is not None:
            ff.fax_file_pages = pages
            update_fields.append('fax_file_pages')

        # Station ID for outbound is our own caller ID, set at send time — do not
        # overwrite it with the remote machine's reported station ID. Only fill it
        # here if it was somehow left blank at creation. For outbound prefer our
        # own caller ID (matches send-time semantics); only then fall back to the
        # remote-reported values.
        if not ff.fax_file_station_id:
            if ff.direction == 'outbound':
                fallback = (ff.fax_file_caller_id_number
                            or fax_local_station_id
                            or fax_remote_station_id or fax_remote_id or fax_header)
            else:
                fallback = (fax_remote_station_id or fax_remote_id or fax_header
                            or ff.fax_file_caller_id_number)
            if fallback:
                ff.fax_file_station_id = fallback
                update_fields.append('fax_file_station_id')

        ff.save(update_fields=update_fields)
        logger.info(f'poll_fax_result: FaxFile {fax_file_uuid} → {new_status}')

        # Notify the fax box owner of the outcome (sent or failed).
        send_fax_status_email.apply_async(args=[str(ff.fax_file_uuid)], countdown=5)

        if ff.tenant_id:
            from apps.client_api.tasks import fire_webhook_event
            event = 'fax.sent' if new_status == 'sent' else 'fax.failed'
            fire_webhook_event.delay(
                str(ff.tenant_id), event, str(ff.fax_file_uuid),
                inline_data={
                    'direction': 'outbound',
                    'fax_file_uuid': str(ff.fax_file_uuid),
                    'fax_uuid': str(ff.fax.fax_uuid) if ff.fax_id else None,
                    'status': new_status,
                    'pages': ff.fax_file_pages,
                    'file_size_bytes': ff.file_size_bytes,
                    'caller_id_number': ff.fax_file_caller_id_number,
                    'destination_number': ff.fax_file_destination_number,
                },
            )

    except self.MaxRetriesExceededError:
        # Timed out waiting — mark failed
        FaxFile.objects.filter(fax_file_uuid=fax_file_uuid, fax_file_status='pending').update(
            fax_file_status='failed'
        )
        logger.warning(
            f'poll_fax_result: TIMEOUT — fax_file_uuid={fax_file_uuid} channel_uuid={channel_uuid} '
            f'polled {_MAX_ATTEMPTS} times over {_MAX_ATTEMPTS * _POLL_INTERVAL}s — channel never disappeared. '
            f'Possible causes: FreeSWITCH hung waiting for T.38 negotiation, stuck txfax process, '
            f'or carrier holding the line open. Check FreeSWITCH logs for this channel UUID.'
        )

        send_fax_status_email.apply_async(args=[fax_file_uuid], countdown=5)

        try:
            ff_timeout = FaxFile.objects.get(fax_file_uuid=fax_file_uuid)
            if ff_timeout.tenant_id:
                from apps.client_api.tasks import fire_webhook_event
                fire_webhook_event.delay(
                    str(ff_timeout.tenant_id), 'fax.failed', str(ff_timeout.fax_file_uuid),
                    inline_data={
                        'direction': 'outbound',
                        'fax_file_uuid': str(ff_timeout.fax_file_uuid),
                        'fax_uuid': str(ff_timeout.fax.fax_uuid) if ff_timeout.fax_id else None,
                        'status': 'failed',
                        'pages': ff_timeout.fax_file_pages,
                        'file_size_bytes': ff_timeout.file_size_bytes,
                        'caller_id_number': ff_timeout.fax_file_caller_id_number,
                        'destination_number': ff_timeout.fax_file_destination_number,
                    },
                )
        except FaxFile.DoesNotExist:
            pass
    except Exception as exc:
        if not isinstance(exc, self.retry.__class__):
            logger.error(f'poll_fax_result: unexpected error for {fax_file_uuid}: {exc}')
            raise self.retry(exc=exc)
        raise


def _smtp_connection():
    """A direct SMTP connection.

    DatabaseEmailBackend (the project default) has no attachment support and
    defers delivery, so fax notifications talk to SMTP directly.
    """
    from django.core.mail import get_connection  # noqa: PLC0415

    return get_connection(
        backend='django.core.mail.backends.smtp.EmailBackend',
        host=settings.EMAIL_HOST,
        port=settings.EMAIL_PORT,
        username=settings.EMAIL_HOST_USER,
        password=settings.EMAIL_HOST_PASSWORD,
        use_tls=settings.EMAIL_USE_TLS,
        use_ssl=settings.EMAIL_USE_SSL,
        fail_silently=False,
    )


def _fax_recipients(fax):
    """Addresses configured on a fax box — fax_email holds one or more, comma/semicolon separated."""
    if not fax:
        return []
    return [addr.strip() for addr in re.split(r'[,;]', fax.fax_email or '') if addr.strip()]


def _last10(value):
    """Last 10 digits of a number, for comparing E.164 against bare/extension forms."""
    digits = re.sub(r'\D', '', value or '')
    return digits[-10:] if len(digits) >= 10 else ''


def _resolve_fax_box(fax_file):
    """Find the fax box a FaxFile belongs to, falling back to the sending number.

    Quick-send (FaxQuickSendView) creates FaxFile rows with fax=None, so the box
    is unknown — but the caller ID it dialled out on is recorded. Match that
    against the boxes' caller ID / extension on last-10 digits, since a box may
    store either an E.164 number or a bare extension. Only boxes that actually
    have an email configured are considered, and the match is scoped to the
    file's tenant when one is known so numbers can't cross tenant boundaries.
    """
    from .models import Fax  # noqa: PLC0415

    if fax_file.fax_id:
        return fax_file.fax

    number = _last10(fax_file.fax_file_caller_id_number)
    if not number:
        return None

    candidates = Fax.objects.exclude(fax_email='')
    if fax_file.tenant_id:
        candidates = candidates.filter(tenant_id=fax_file.tenant_id)

    # insert_date order makes a multi-box tie deterministic rather than arbitrary.
    matches = [
        f for f in candidates.order_by('insert_date')
        if _last10(f.fax_caller_id_number) == number or _last10(f.fax_extension) == number
    ]
    if not matches:
        return None
    if len(matches) > 1:
        logger.warning(
            '_resolve_fax_box: number %s matches %d fax boxes (%s) — using %r',
            fax_file.fax_file_caller_id_number, len(matches),
            ', '.join(f.fax_name for f in matches), matches[0].fax_name,
        )
    return matches[0]


@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def send_fax_status_email(self, fax_file_uuid: str):
    """Email the outbound result (sent or failed) to the fax box's configured address.

    Queued once the fax reaches a terminal status. Quick-send faxes carry no fax
    box, so the box is backtraced from the sending caller ID — see _resolve_fax_box.
    """
    from django.core.mail import EmailMultiAlternatives  # noqa: PLC0415
    from .models import FaxFile  # noqa: PLC0415

    try:
        ff = FaxFile.objects.select_related('fax').get(fax_file_uuid=fax_file_uuid)
    except FaxFile.DoesNotExist:
        logger.warning('send_fax_status_email: FaxFile %s not found', fax_file_uuid)
        return

    # Quick-send rows have no fax box; fall back to the sending number.
    fax = _resolve_fax_box(ff)
    recipients = _fax_recipients(fax)
    if not recipients:
        logger.info(
            'send_fax_status_email: no fax_email resolved (fax box %s, from %s) — skipping %s',
            ff.fax_id, ff.fax_file_caller_id_number or '?', fax_file_uuid,
        )
        return

    succeeded = ff.fax_file_status == 'sent'
    destination = ff.fax_file_destination_number or 'Unknown'
    pages = ff.fax_file_pages or 0
    doc_name = ff.fax_file_name or ''
    sent_at = ff.fax_file_date

    outcome = 'delivered successfully' if succeeded else 'failed to send'
    subject = (
        f'Fax to {destination} {"sent" if succeeded else "FAILED"}'
        + (f' — {pages} page(s)' if succeeded else '')
    )

    rows = [
        ('To', destination),
        ('From', ff.fax_file_caller_id_number or ''),
        ('Document', doc_name),
        ('Pages', str(pages)),
        ('Submitted', sent_at.strftime('%Y-%m-%d %H:%M:%S %Z') if sent_at else ''),
        ('Status', 'Sent' if succeeded else 'Failed'),
    ]

    text_body = f'Your fax {outcome}.\n\n' + ''.join(
        f'{label}: {value}\n' for label, value in rows if value
    )
    if not succeeded:
        text_body += '\nPlease verify the destination number and try again.\n'

    html_rows = ''.join(
        f'<tr><td style="padding:2px 10px 2px 0"><b>{label}:</b></td><td>{value}</td></tr>'
        for label, value in rows if value
    )
    html_body = (
        f'<html><body>'
        f'<p>Your fax <b>{outcome}</b>.</p>'
        f'<table>{html_rows}</table>'
        + ('' if succeeded else '<p>Please verify the destination number and try again.</p>')
        + f'</body></html>'
    )

    try:
        reply_to = getattr(settings, 'EMAIL_REPLY_TO', None) or getattr(settings, 'DEFAULT_FROM_EMAIL', None)
        email = EmailMultiAlternatives(
            subject=subject,
            body=text_body,
            from_email=settings.EMAIL_HOST_USER,
            to=recipients,
            reply_to=[reply_to] if reply_to else None,
            connection=_smtp_connection(),
        )
        email.attach_alternative(html_body, 'text/html')
        email.send(fail_silently=False)
        logger.info(
            'send_fax_status_email: SENT (%s) to %s for FaxFile %s',
            ff.fax_file_status, ', '.join(recipients), fax_file_uuid,
        )
    except Exception as exc:
        logger.error('send_fax_status_email: failed for %s: %s', fax_file_uuid, exc)
        raise self.retry(exc=exc, countdown=30)


@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def send_fax_email(self, fax_file_uuid: str):
    """Email a received inbound fax to the fax box's configured email address.

    Attaches the fax file (PDF preferred over TIFF) directly via SMTP,
    bypassing DatabaseEmailBackend which has no attachment support.
    """
    from django.core.mail import EmailMultiAlternatives  # noqa: PLC0415
    from .models import FaxFile  # noqa: PLC0415

    try:
        ff = FaxFile.objects.select_related('fax').get(fax_file_uuid=fax_file_uuid)
    except FaxFile.DoesNotExist:
        logger.warning('send_fax_email: FaxFile %s not found', fax_file_uuid)
        return

    fax = ff.fax
    recipients = _fax_recipients(fax)
    if not fax or not recipients:
        logger.info('send_fax_email: no fax_email configured for fax box — skipping %s', fax_file_uuid)
        return

    # Ensure we are sending a PDF (convert from TIFF if needed)
    file_path = ff.fax_file_path or ''
    if file_path.endswith('.tif'):
        try:
            from .utils import tiff_to_pdf
            file_path = tiff_to_pdf(file_path)
        except Exception as conv_err:
            logger.warning('send_fax_email: TIFF→PDF conversion failed for %s: %s', file_path, conv_err)
            # Fall back to the original TIFF if conversion fails

    if not file_path or not os.path.isfile(file_path):
        logger.warning('send_fax_email: fax file not found on disk: %s — retrying', file_path)
        raise self.retry(exc=FileNotFoundError(f'Fax file not found: {file_path}'), countdown=30)

    cid_name = ff.fax_file_caller_id_name or ''
    cid_number = ff.fax_file_caller_id_number or 'Unknown'
    pages = ff.fax_file_pages or 0
    ext = os.path.splitext(file_path)[1].lower()
    mime_type = 'application/pdf' if ext == '.pdf' else 'image/tiff'

    subject = f'Incoming fax from {cid_name or cid_number} — {pages} page(s)'
    text_body = (
        f'You have received a new fax.\n\n'
        f'From: {cid_name} <{cid_number}>\n'
        f'Pages: {pages}\n'
    )
    html_body = (
        f'<html><body>'
        f'<p>You have received a new fax.</p>'
        f'<table>'
        f'<tr><td><b>From:</b></td><td>{cid_name} &lt;{cid_number}&gt;</td></tr>'
        f'<tr><td><b>Pages:</b></td><td>{pages}</td></tr>'
        f'</table>'
        f'<p>The fax is attached to this email.</p>'
        f'</body></html>'
    )

    try:
        smtp_connection = _smtp_connection()

        reply_to = getattr(settings, 'EMAIL_REPLY_TO', None) or getattr(settings, 'DEFAULT_FROM_EMAIL', None)
        email = EmailMultiAlternatives(
            subject=subject,
            body=text_body,
            from_email=settings.EMAIL_HOST_USER,
            to=recipients,
            reply_to=[reply_to] if reply_to else None,
            connection=smtp_connection,
        )
        email.attach_alternative(html_body, 'text/html')

        with open(file_path, 'rb') as f:
            email.attach(os.path.basename(file_path), f.read(), mime_type)

        attach_size = sum(len(a[1]) for a in email.attachments if isinstance(a[1], (bytes, bytearray)))
        logger.info(
            'send_fax_email: sending to %s for FaxFile %s — file=%s attachments=%d bytes=%d',
            ', '.join(recipients), fax_file_uuid, file_path, len(email.attachments), attach_size,
        )
        email.send(fail_silently=False)
        logger.info('send_fax_email: SENT to %s for FaxFile %s', ', '.join(recipients), fax_file_uuid)

    except Exception as exc:
        logger.error('send_fax_email: failed for %s: %s', fax_file_uuid, exc)
        raise self.retry(exc=exc, countdown=30)


@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def upload_fax_to_ftp(self, fax_file_uuid: str):
    """Upload a received inbound fax to the fax box's configured FTP/FTPS server.

    Converts TIFF→PDF (best effort) before upload, then stores the file under the
    box's configured remote path using Python's stdlib ftplib.
    """
    from ftplib import FTP, FTP_TLS, error_perm  # noqa: PLC0415
    from django.utils import timezone  # noqa: PLC0415
    from .models import FaxFile, FaxFtpDelivery  # noqa: PLC0415

    try:
        ff = FaxFile.objects.select_related('fax').get(fax_file_uuid=fax_file_uuid)
    except FaxFile.DoesNotExist:
        logger.warning('upload_fax_to_ftp: FaxFile %s not found', fax_file_uuid)
        return

    fax = ff.fax
    if not fax or not fax.fax_ftp_host:
        logger.info('upload_fax_to_ftp: no FTP host configured — skipping %s', fax_file_uuid)
        return

    # One audit row per fax file, updated in place across retry attempts so the
    # admin shows current status (mirrors WebhookDelivery). Never let logging
    # bookkeeping break the actual upload.
    delivery, _ = FaxFtpDelivery.objects.get_or_create(
        fax_file=ff,
        defaults={'fax': fax, 'tenant_id': getattr(fax, 'tenant_id', None)},
    )

    # Prefer a PDF (convert from TIFF if needed)
    file_path = ff.fax_file_path or ''
    if file_path.endswith('.tif'):
        try:
            from .utils import tiff_to_pdf
            file_path = tiff_to_pdf(file_path)
        except Exception as conv_err:
            logger.warning('upload_fax_to_ftp: TIFF→PDF conversion failed for %s: %s', file_path, conv_err)
            # Fall back to the original TIFF if conversion fails

    if not file_path or not os.path.isfile(file_path):
        logger.warning('upload_fax_to_ftp: fax file not found on disk: %s — retrying', file_path)
        raise self.retry(exc=FileNotFoundError(f'Fax file not found: {file_path}'), countdown=30)

    host = fax.fax_ftp_host
    port = fax.fax_ftp_port or 21
    username = fax.fax_ftp_username or 'anonymous'
    password = fax.fax_ftp_password or ''
    remote_path = (fax.fax_ftp_path or '').strip()
    remote_name = os.path.basename(file_path)
    use_tls = bool(fax.fax_ftp_use_tls)
    file_size = os.path.getsize(file_path)

    attempt_no = self.request.retries + 1
    logger.info(
        'upload_fax_to_ftp[%s]: starting — %s (%d bytes) -> %s%s://%s@%s:%d path=%r (attempt %d/%d)',
        fax_file_uuid, remote_name, file_size,
        'STARTTLS ' if use_tls else '', 'ftps' if use_tls else 'ftp',
        username, host, port, remote_path,
        attempt_no, self.max_retries + 1,
    )

    # Snapshot the target + mark this attempt on the audit row.
    delivery.host = host
    delivery.port = port
    delivery.username = username
    delivery.remote_path = remote_path
    delivery.remote_name = remote_name
    delivery.use_tls = use_tls
    delivery.file_size_bytes = file_size
    delivery.attempts = attempt_no
    delivery.status = FaxFtpDelivery.STATUS_PENDING
    delivery.save()

    started = time.monotonic()
    try:
        ftp = FTP_TLS() if use_tls else FTP()

        logger.debug('upload_fax_to_ftp[%s]: connecting to %s:%d (timeout=30s)', fax_file_uuid, host, port)
        welcome = ftp.connect(host, port, timeout=30)
        logger.debug('upload_fax_to_ftp[%s]: connected — server says: %s', fax_file_uuid, welcome)

        logger.debug('upload_fax_to_ftp[%s]: logging in as %r', fax_file_uuid, username)
        ftp.login(username, password)
        logger.debug('upload_fax_to_ftp[%s]: login OK', fax_file_uuid)

        if isinstance(ftp, FTP_TLS):
            ftp.prot_p()  # encrypt the data channel
            logger.debug('upload_fax_to_ftp[%s]: TLS data channel protection enabled', fax_file_uuid)

        # Change into the configured directory, creating it if missing.
        if remote_path:
            for segment in remote_path.strip('/').split('/'):
                if not segment:
                    continue
                try:
                    ftp.cwd(segment)
                    logger.debug('upload_fax_to_ftp[%s]: cwd %r', fax_file_uuid, segment)
                except error_perm:
                    logger.info('upload_fax_to_ftp[%s]: dir %r missing — creating it', fax_file_uuid, segment)
                    ftp.mkd(segment)
                    ftp.cwd(segment)
            logger.debug('upload_fax_to_ftp[%s]: now in remote dir %s', fax_file_uuid, ftp.pwd())

        logger.debug('upload_fax_to_ftp[%s]: STOR %s (%d bytes)', fax_file_uuid, remote_name, file_size)
        with open(file_path, 'rb') as f:
            resp = ftp.storbinary(f'STOR {remote_name}', f)
        logger.debug('upload_fax_to_ftp[%s]: STOR response: %s', fax_file_uuid, resp)
        ftp.quit()

        logger.info(
            'upload_fax_to_ftp[%s]: SUCCESS — uploaded %s (%d bytes) to %s:%d/%s in %.2fs',
            fax_file_uuid, remote_name, file_size, host, port, remote_path,
            time.monotonic() - started,
        )
        delivery.status = FaxFtpDelivery.STATUS_SUCCESS
        delivery.last_response = str(resp)
        delivery.last_error = ''
        delivery.delivered_at = timezone.now()
        delivery.save(update_fields=['status', 'last_response', 'last_error', 'delivered_at'])
    except Exception as exc:
        # exc_info=True logs the full traceback so transient vs. config errors
        # (auth failure, refused connection, permission denied) are distinguishable.
        logger.error(
            'upload_fax_to_ftp[%s]: FAILED after %.2fs (attempt %d/%d) connecting %s@%s:%d — %s: %s',
            fax_file_uuid, time.monotonic() - started,
            attempt_no, self.max_retries + 1,
            username, host, port, type(exc).__name__, exc,
            exc_info=True,
        )
        # Mark failed; final attempt stays 'failed', earlier ones will flip back
        # to 'pending' on the next retry's start block above.
        delivery.status = FaxFtpDelivery.STATUS_FAILED
        delivery.last_error = f'{type(exc).__name__}: {exc}'
        delivery.save(update_fields=['status', 'last_error'])
        raise self.retry(exc=exc, countdown=30)
