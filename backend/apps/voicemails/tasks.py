"""Celery tasks for the voicemails app."""
import logging
import os
import random
import wave

from celery import shared_task
from django.conf import settings

logger = logging.getLogger(__name__)


def _split_emails(value):
    """Split a comma-separated voicemail_mail_to into a clean recipient list."""
    if not value:
        return []
    return [a.strip() for a in str(value).split(',') if a.strip()]


def _get_wav_duration(file_path: str) -> int:
    """Return WAV duration in seconds (minimum 1 for non-empty files), or 0 on error."""
    try:
        with wave.open(file_path, 'r') as wf:
            nframes = wf.getnframes()
            if nframes == 0:
                return 0
            return max(1, round(nframes / wf.getframerate()))
    except Exception:
        return 0


def _update_message_len_if_zero(message_uuid: str, actual_len: int) -> None:
    """Update message_len in the DB if it was stored as 0 but we now know the real value."""
    if actual_len <= 0:
        return
    try:
        from .models import VoicemailMessage  # noqa: PLC0415
        updated = VoicemailMessage.objects.using('voicemail_sqlite').filter(
            uuid=message_uuid, message_len=0,
        ).update(message_len=actual_len)
        if updated:
            logger.info('[VM] corrected message_len=%d for %s', actual_len, message_uuid)
    except Exception:
        logger.exception('[VM] failed to update message_len for %s', message_uuid)


def _resolve_audio_file(message_uuid: str, file_path: str) -> str:
    """Return the best available path to the voicemail audio file.

    Checks the task-argument path first; if the file isn't on disk yet,
    falls back to the path stored in the VoicemailMessage DB record (written
    by FreeSWITCH). Returns an empty string if neither path resolves.
    """
    logger.info('[VM-AUDIO] _resolve_audio_file: message=%s arg_path=%s exists=%s',
                message_uuid, file_path, os.path.isfile(file_path) if file_path else False)

    if file_path and os.path.isfile(file_path):
        logger.info('[VM-AUDIO] _resolve_audio_file: arg path OK — using %s', file_path)
        return file_path

    # Fallback: look up the path FreeSWITCH wrote into the DB
    logger.info('[VM-AUDIO] _resolve_audio_file: arg path not found, querying voicemail_sqlite DB')
    try:
        from .models import VoicemailMessage  # noqa: PLC0415
        msg = VoicemailMessage.objects.using('voicemail_sqlite').filter(uuid=message_uuid).first()
        if msg:
            logger.info('[VM-AUDIO] _resolve_audio_file: DB record found — file_path=%s exists=%s',
                        msg.file_path, os.path.isfile(msg.file_path) if msg.file_path else False)
            if msg.file_path and os.path.isfile(msg.file_path):
                return msg.file_path
        else:
            logger.warning('[VM-AUDIO] _resolve_audio_file: no DB record found for message %s', message_uuid)
    except Exception:
        logger.exception('[VM-AUDIO] _resolve_audio_file: DB lookup failed for message %s', message_uuid)

    logger.warning('[VM-AUDIO] _resolve_audio_file: FAILED to find audio for message %s (tried arg: %s)',
                   message_uuid, file_path)
    return ''


def _send_voicemail_email(vm, message_uuid: str, file_path: str, cid_name: str, cid_number: str,
                          message_len: int, transcript_text: str) -> None:
    """Send a voicemail notification email with the audio file attached.

    Respects the mailbox ``voicemail_file`` setting:
      * ``'attach'`` – attach the WAV file (default)
      * ``'link'``   – send without attachment (link would come from a portal)
      * ``'none'``   – send without attachment

    Args:
        vm: Voicemail model instance.
        message_uuid: UUID of the voicemail message.
        file_path: Absolute path to the WAV audio file on disk.
        cid_name: Caller-ID name.
        cid_number: Caller-ID number.
        message_len: Duration of the voicemail in seconds.
        transcript_text: Transcribed text or a fallback string such as 'Not available'.
    """
    from django.core.mail import EmailMultiAlternatives as _EmailMultiAlternatives, get_connection  # noqa: PLC0415

    # Bypass DatabaseEmailBackend — it has no attachment support (stores only text fields).
    # Build a direct SMTP connection identical to how send_pending_emails delivers queued mail.
    smtp_connection = get_connection(
        backend='django.core.mail.backends.smtp.EmailBackend',
        host=settings.EMAIL_HOST,
        port=settings.EMAIL_PORT,
        username=settings.EMAIL_HOST_USER,
        password=settings.EMAIL_HOST_PASSWORD,
        use_tls=settings.EMAIL_USE_TLS,
        use_ssl=settings.EMAIL_USE_SSL,
        fail_silently=False,
    )

    logger.info(
        '[VM-EMAIL] _send_voicemail_email: message=%s vm=%s mail_to=%s on_new_message=%s voicemail_file=%s',
        message_uuid, vm.voicemail_id, vm.voicemail_mail_to,
        vm.voicemail_on_new_message, vm.voicemail_file,
    )

    if not vm.voicemail_mail_to:
        logger.warning('[VM-EMAIL] _send_voicemail_email: SKIP — voicemail_mail_to is empty for %s', message_uuid)
        return
    if vm.voicemail_on_new_message not in ('email', 'both'):
        logger.warning('[VM-EMAIL] _send_voicemail_email: SKIP — on_new_message=%s for %s',
                       vm.voicemail_on_new_message, message_uuid)
        return

    subject = f'New voicemail from {cid_name or cid_number or "unknown"} for {vm.voicemail_id}'
    text_body = (
        f'You have a new voicemail message.\n\n'
        f'From: {cid_name} <{cid_number}>\n'
        f'Duration: {message_len} seconds\n'
        f'\nTranscript:\n{transcript_text or "Not available"}\n'
    )
    html_body = (
        f'<html><body>'
        f'<p>You have a new voicemail message.</p>'
        f'<table>'
        f'<tr><td><b>From:</b></td><td>{cid_name} &lt;{cid_number}&gt;</td></tr>'
        f'<tr><td><b>Duration:</b></td><td>{message_len} seconds</td></tr>'
        f'</table>'
        f'<p><b>Transcript:</b><br>{transcript_text or "Not available"}</p>'
        f'</body></html>'
    )
    reply_to = getattr(settings, 'EMAIL_REPLY_TO', None) or getattr(settings, 'DEFAULT_FROM_EMAIL', None)
    email = _EmailMultiAlternatives(
        subject=subject,
        body=text_body,
        from_email=settings.EMAIL_HOST_USER,
        to=_split_emails(vm.voicemail_mail_to),
        reply_to=[reply_to] if reply_to else None,
        connection=smtp_connection,
    )
    email.attach_alternative(html_body, 'text/html')

    # Attach audio only when the mailbox setting allows it
    if vm.voicemail_file == 'attach':
        resolved_path = _resolve_audio_file(message_uuid, file_path)
        if resolved_path:
            with open(resolved_path, 'rb') as f:
                # Use application/octet-stream instead of audio/wav —
                # Exchange Online silently strips audio/wav on inbound delivery.
                email.attach(os.path.basename(resolved_path), f.read(), 'application/octet-stream')
            logger.info('[VM-EMAIL] _send_voicemail_email: attached %s for message %s', resolved_path, message_uuid)
        else:
            logger.warning(
                '[VM-EMAIL] _send_voicemail_email: voicemail_file=attach but audio NOT found on disk '
                'for message %s — sending without attachment', message_uuid
            )
    else:
        logger.info('[VM-EMAIL] _send_voicemail_email: voicemail_file=%s — skipping attachment for message %s',
                    vm.voicemail_file, message_uuid)

    attach_count = len(email.attachments)
    attach_size = sum(len(a[1]) for a in email.attachments if isinstance(a[1], (bytes, bytearray)))
    logger.info('[VM-EMAIL] _send_voicemail_email: sending to %s — attachments=%d total_bytes=%d',
                vm.voicemail_mail_to, attach_count, attach_size)
    email.send(fail_silently=False)
    logger.info('[VM-EMAIL] _send_voicemail_email: SENT to %s for message %s', vm.voicemail_mail_to, message_uuid)


def _transcribe_send_fallback_email(vm_uuid: str, message_uuid: str, file_path: str,
                                    cid_name: str, cid_number: str, message_len: int) -> None:
    """Send a fallback voicemail email when transcription has exhausted all retries.

    Uses 'Not available' as the transcript text.
    """
    if not vm_uuid:
        return
    try:
        from .models import Voicemail  # noqa: PLC0415
        vm = Voicemail.objects.select_related('tenant', 'domain__tenant').filter(
            voicemail_uuid=vm_uuid
        ).first()
        if vm:
            logger.warning(
                '_transcribe_send_fallback_email: sending fallback email for %s (transcript not available)',
                message_uuid,
            )
            _send_voicemail_email(vm, message_uuid, file_path, cid_name, cid_number,
                                  message_len, 'Not available')
    except Exception:
        logger.exception('_transcribe_send_fallback_email: failed for message %s', message_uuid)


@shared_task(bind=True, max_retries=3, default_retry_delay=30, acks_late=True)
def transcribe_voicemail_google(
    self,
    message_uuid: str,
    file_path: str,
    vm_uuid: str = None,
    domain: str = None,
    cid_name: str = '',
    cid_number: str = '',
    message_len: int = 0,
    created_epoch: int = 0,
):
    """
    Transcribe a voicemail audio file using Google Cloud Speech-to-Text v1 API.
    Uses an API key for authentication. Auto-detects language.
    """
    import base64
    import requests
    from .models import VoicemailTranscript  # noqa: PLC0415

    transcript_obj, _ = VoicemailTranscript.objects.get_or_create(
        message_uuid=message_uuid,
        defaults={'status': VoicemailTranscript.STATUS_PENDING},
    )

    if not os.path.isfile(file_path):
        logger.warning('transcribe_voicemail_google: file not ready yet, retrying: %s', file_path)
        raise self.retry(exc=Exception(f'Audio file not found: {file_path}'), countdown=15)

    if message_len == 0:
        message_len = _get_wav_duration(file_path)
        _update_message_len_if_zero(message_uuid, message_len)

    if message_len == 0:
        logger.info('transcribe_voicemail_google: skipping transcription for empty voicemail %s', message_uuid)
        transcript_obj.status = VoicemailTranscript.STATUS_FAILED
        transcript_obj.error = 'Empty audio file'
        transcript_obj.save(update_fields=['status', 'error', 'updated_at'])
        return

    api_key = getattr(settings, 'GOOGLE_SPEECH_API_KEY', '')
    if not api_key:
        logger.error('transcribe_voicemail_google: GOOGLE_SPEECH_API_KEY is not set')
        transcript_obj.status = VoicemailTranscript.STATUS_FAILED
        transcript_obj.error = 'GOOGLE_SPEECH_API_KEY not configured'
        transcript_obj.save(update_fields=['status', 'error', 'updated_at'])
        return

    try:
        with open(file_path, 'rb') as f:
            audio_content = base64.b64encode(f.read()).decode('utf-8')

        resp = requests.post(
            'https://speech.googleapis.com/v1/speech:recognize',
            params={'key': api_key},
            json={
                'config': {
                    'encoding': 'LINEAR16',
                    'sampleRateHertz': 8000,
                    'languageCode': 'en-US',
                    'enableAutomaticPunctuation': True,
                    'model': 'phone_call',
                    'useEnhanced': True,
                },
                'audio': {'content': audio_content},
            },
            timeout=120,
        )
        resp.raise_for_status()

        results = resp.json().get('results', [])
        transcript_text = ' '.join(
            r.get('alternatives', [{}])[0].get('transcript', '')
            for r in results
        ).strip()
        confidence = (
            results[0].get('alternatives', [{}])[0].get('confidence')
            if results else None
        )

        transcript_obj.transcript = transcript_text
        transcript_obj.confidence = confidence
        transcript_obj.status = VoicemailTranscript.STATUS_DONE
        transcript_obj.error = ''
        transcript_obj.save(update_fields=['transcript', 'confidence', 'status', 'error', 'updated_at'])
        logger.info('transcribe_voicemail_google: done for %s', message_uuid)

        # Fire webhook and email now that transcript is ready
        if vm_uuid:
            try:
                from .models import Voicemail  # noqa: PLC0415
                vm = Voicemail.objects.select_related('tenant', 'domain__tenant').filter(
                    voicemail_uuid=vm_uuid
                ).first()
                if vm:
                    _tenant = vm.tenant or (vm.domain.tenant if vm.domain_id else None)
                    if _tenant:
                        from django.conf import settings as _settings  # noqa: PLC0415
                        from apps.client_api.tasks import fire_webhook_event  # noqa: PLC0415
                        tenant_uuid = str(_tenant.tenant_uuid)
                        base_url = getattr(_settings, 'PUBLIC_BASE_URL', '').rstrip('/')
                        audio_url = f'{base_url}/api/v1/client/{tenant_uuid}/voicemail-messages/{message_uuid}/audio/'
                        fire_webhook_event.delay(
                            tenant_uuid,
                            'voicemail.received',
                            message_uuid,
                            inline_data={
                                'uuid': message_uuid,
                                'caller_id_number': cid_number,
                                'caller_id_name': cid_name,
                                'message_length': message_len,
                                'created_epoch': created_epoch,
                                'read': False,
                                'audio_url': audio_url,
                                'transcript': transcript_text,
                                'voicemail_id': str(vm.voicemail_id),
                                'tenant_id': tenant_uuid,
                            },
                        )

                    # Send email with transcript and audio attachment
                    _send_voicemail_email(
                        vm, message_uuid, file_path, cid_name, cid_number,
                        message_len, transcript_text,
                    )
            except Exception:
                logger.exception('transcribe_voicemail_google: post-transcription tasks failed for %s', message_uuid)

    except requests.HTTPError as exc:
        delay = min(120, (2 ** self.request.retries) * 30 + random.uniform(1, 5))
        logger.error('transcribe_voicemail_google: HTTP error for %s: %s (retry in %.0fs)', message_uuid, exc, delay)
        transcript_obj.status = VoicemailTranscript.STATUS_FAILED
        transcript_obj.error = str(exc)
        transcript_obj.save(update_fields=['status', 'error', 'updated_at'])
        if self.request.retries >= self.max_retries:
            # All retries exhausted — send fallback email with "Not available"
            _transcribe_send_fallback_email(vm_uuid, message_uuid, file_path, cid_name, cid_number, message_len)
        raise self.retry(exc=exc, countdown=delay)
    except Exception as exc:
        logger.error('transcribe_voicemail_google: error for %s: %s', message_uuid, exc)
        transcript_obj.status = VoicemailTranscript.STATUS_FAILED
        transcript_obj.error = str(exc)
        transcript_obj.save(update_fields=['status', 'error', 'updated_at'])
        if self.request.retries >= self.max_retries:
            # All retries exhausted — send fallback email with "Not available"
            _transcribe_send_fallback_email(vm_uuid, message_uuid, file_path, cid_name, cid_number, message_len)
        raise self.retry(exc=exc, countdown=30)


@shared_task(bind=True, max_retries=3, default_retry_delay=30, acks_late=True)
def transcribe_voicemail_gemini(
    self,
    message_uuid: str,
    file_path: str,
    vm_uuid: str = None,
    domain: str = None,
    cid_name: str = '',
    cid_number: str = '',
    message_len: int = 0,
    created_epoch: int = 0,
):
    """
    Transcribe a voicemail audio file using Google Gemini 2.5 Flash via the
    google-genai SDK.  Uploads the WAV file to the Gemini File API, requests
    a structured transcription, and stores the result in VoicemailTranscript.

    After a successful transcription the task also fires the voicemail.received
    webhook event and sends the voicemail notification email — matching the
    behaviour of transcribe_voicemail_google.

    Required settings / env vars:
        GEMINI_API_KEY  — Gemini API key (same key used by app.py demo)
    """
    from google import genai as _genai  # noqa: PLC0415
    from .models import VoicemailTranscript  # noqa: PLC0415

    logger.info(
        '[VM-GEMINI] transcribe_voicemail_gemini: START message=%s file=%s',
        message_uuid, file_path,
    )

    transcript_obj, _ = VoicemailTranscript.objects.get_or_create(
        message_uuid=message_uuid,
        defaults={'status': VoicemailTranscript.STATUS_PENDING},
    )

    # ── Resolve audio path ────────────────────────────────────────────────
    resolved_path = _resolve_audio_file(message_uuid, file_path)
    if not resolved_path:
        logger.warning('[VM-GEMINI] transcribe_voicemail_gemini: file not ready, retrying: %s', file_path)
        raise self.retry(exc=Exception(f'Audio file not found: {file_path}'), countdown=15)

    if message_len == 0:
        message_len = _get_wav_duration(resolved_path)
        _update_message_len_if_zero(message_uuid, message_len)

    if message_len == 0:
        logger.info('[VM-GEMINI] skipping transcription for empty voicemail %s', message_uuid)
        transcript_obj.status = VoicemailTranscript.STATUS_FAILED
        transcript_obj.error = 'Empty audio file'
        transcript_obj.save(update_fields=['status', 'error', 'updated_at'])
        return

    # ── Validate API key ──────────────────────────────────────────────────
    api_key = getattr(settings, 'GEMINI_API_KEY', '') or os.environ.get('GEMINI_API_KEY', '')
    if not api_key:
        logger.error('[VM-GEMINI] transcribe_voicemail_gemini: GEMINI_API_KEY is not set')
        transcript_obj.status = VoicemailTranscript.STATUS_FAILED
        transcript_obj.error = 'GEMINI_API_KEY not configured'
        transcript_obj.save(update_fields=['status', 'error', 'updated_at'])
        return

    try:
        gemini_client = _genai.Client(api_key=api_key)

        # ── Upload WAV to Gemini File API ─────────────────────────────────
        logger.info('[VM-GEMINI] transcribe_voicemail_gemini: uploading %s to Gemini Files API', resolved_path)
        uploaded_file = gemini_client.files.upload(file=resolved_path)
        logger.info('[VM-GEMINI] transcribe_voicemail_gemini: upload OK — uri=%s', uploaded_file.uri)

        # ── Build prompt ──────────────────────────────────────────────────
        caller_hint = f'Caller: {cid_name or cid_number or "Unknown"}' if (cid_name or cid_number) else ''
        prompt = f"""Transcribe this voicemail message accurately.

{caller_hint}

Requirements:
- If multiple speakers are identifiable, add speaker labels (e.g. Caller:, Recipient:)
- Use clean, readable formatting with proper punctuation
- Ignore background noise, hold music, and dial tones
- Return plain text only — no markdown, no commentary
- Capture every word spoken; do not summarise"""

        # ── Generate transcription ────────────────────────────────────────
        logger.info('[VM-GEMINI] transcribe_voicemail_gemini: requesting transcription from gemini-2.5-flash')
        response = gemini_client.models.generate_content(
            model='gemini-2.5-flash',
            contents=[prompt, uploaded_file],
        )
        transcript_text = (response.text or '').strip()

        # ── Persist result ────────────────────────────────────────────────
        transcript_obj.transcript = transcript_text
        transcript_obj.confidence = None  # Gemini does not expose a confidence score
        transcript_obj.status = VoicemailTranscript.STATUS_DONE
        transcript_obj.error = ''
        transcript_obj.save(update_fields=['transcript', 'confidence', 'status', 'error', 'updated_at'])
        logger.info('[VM-GEMINI] transcribe_voicemail_gemini: DONE for %s — chars=%d', message_uuid, len(transcript_text))

        # ── Post-transcription: webhook + email ───────────────────────────
        if vm_uuid:
            try:
                from .models import Voicemail  # noqa: PLC0415
                vm = Voicemail.objects.select_related('tenant', 'domain__tenant').filter(
                    voicemail_uuid=vm_uuid
                ).first()
                if vm:
                    _tenant = vm.tenant or (vm.domain.tenant if vm.domain_id else None)
                    if _tenant:
                        from django.conf import settings as _settings  # noqa: PLC0415
                        from apps.client_api.tasks import fire_webhook_event  # noqa: PLC0415
                        tenant_uuid = str(_tenant.tenant_uuid)
                        base_url = getattr(_settings, 'PUBLIC_BASE_URL', '').rstrip('/')
                        audio_url = f'{base_url}/api/v1/client/{tenant_uuid}/voicemail-messages/{message_uuid}/audio/'
                        fire_webhook_event.delay(
                            tenant_uuid,
                            'voicemail.received',
                            message_uuid,
                            inline_data={
                                'uuid': message_uuid,
                                'caller_id_number': cid_number,
                                'caller_id_name': cid_name,
                                'message_length': message_len,
                                'created_epoch': created_epoch,
                                'read': False,
                                'audio_url': audio_url,
                                'transcript': transcript_text,
                                'voicemail_id': str(vm.voicemail_id),
                                'tenant_id': tenant_uuid,
                            },
                        )

                    # Send email with transcript and audio attachment
                    _send_voicemail_email(
                        vm, message_uuid, file_path, cid_name, cid_number,
                        message_len, transcript_text,
                    )
            except Exception:
                logger.exception(
                    '[VM-GEMINI] transcribe_voicemail_gemini: post-transcription tasks failed for %s', message_uuid,
                )

    except Exception as exc:
        delay = min(120, (2 ** self.request.retries) * 30 + random.uniform(1, 5))
        logger.error(
            '[VM-GEMINI] transcribe_voicemail_gemini: error for %s: %s (retry in %.0fs)',
            message_uuid, exc, delay,
        )
        transcript_obj.status = VoicemailTranscript.STATUS_FAILED
        transcript_obj.error = str(exc)
        transcript_obj.save(update_fields=['status', 'error', 'updated_at'])
        if self.request.retries >= self.max_retries:
            _transcribe_send_fallback_email(vm_uuid, message_uuid, file_path, cid_name, cid_number, message_len)
        raise self.retry(exc=exc, countdown=delay)


@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def transcribe_voicemail(self, message_uuid: str, file_path: str):
    """
    Transcribe a voicemail audio file using Deepgram and store the result
    in VoicemailTranscript.

    Called after ingest when voicemail_transcription_enabled=True on the mailbox.
    """
    from .models import VoicemailTranscript  # noqa: PLC0415

    transcript_obj, _ = VoicemailTranscript.objects.get_or_create(
        message_uuid=message_uuid,
        defaults={'status': VoicemailTranscript.STATUS_PENDING},
    )

    if not os.path.isfile(file_path):
        logger.error('transcribe_voicemail: file not found: %s', file_path)
        transcript_obj.status = VoicemailTranscript.STATUS_FAILED
        transcript_obj.error = f'Audio file not found: {file_path}'
        transcript_obj.save(update_fields=['status', 'error', 'updated_at'])
        return

    api_key = getattr(settings, 'DEEPGRAM_API_KEY', '')
    if not api_key:
        logger.error('transcribe_voicemail: DEEPGRAM_API_KEY is not set')
        transcript_obj.status = VoicemailTranscript.STATUS_FAILED
        transcript_obj.error = 'DEEPGRAM_API_KEY not configured'
        transcript_obj.save(update_fields=['status', 'error', 'updated_at'])
        return

    try:
        from deepgram import DeepgramClient, PrerecordedOptions, FileSource  # noqa: PLC0415

        client = DeepgramClient(api_key)

        with open(file_path, 'rb') as audio_file:
            buffer_data = audio_file.read()

        payload: FileSource = {'buffer': buffer_data}
        options = PrerecordedOptions(
            model='nova-2',
            smart_format=True,
            punctuate=True,
        )

        response = client.listen.prerecorded.v('1').transcribe_file(payload, options)

        result = response.results.channels[0].alternatives[0]
        transcript_text = result.transcript
        confidence = result.confidence

        transcript_obj.transcript = transcript_text
        transcript_obj.confidence = confidence
        transcript_obj.status = VoicemailTranscript.STATUS_DONE
        transcript_obj.error = ''
        transcript_obj.save(update_fields=['transcript', 'confidence', 'status', 'error', 'updated_at'])
        logger.info('transcribe_voicemail: done for %s (confidence=%.2f)', message_uuid, confidence or 0)

    except Exception as exc:
        logger.error('transcribe_voicemail: error for %s: %s', message_uuid, exc)
        transcript_obj.status = VoicemailTranscript.STATUS_FAILED
        transcript_obj.error = str(exc)
        transcript_obj.save(update_fields=['status', 'error', 'updated_at'])
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=10)
def reload_voicemail(self, voicemail_uuid: str):
    """Trigger a FreeSWITCH XML reload after a voicemail change.

    Voicemail configuration is read by FreeSWITCH from the database, so this
    triggers a ``reloadxml`` to pick up any changes.
    """
    try:
        from esl.tasks import reload_xml  # noqa: PLC0415
        reload_xml.delay()
        logger.info('reload_voicemail: triggered reloadxml for voicemail %s', voicemail_uuid)
    except Exception as exc:
        logger.warning(
            'reload_voicemail: ESL task failed for %s: %s – retrying',
            voicemail_uuid,
            exc,
        )
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=15)
def send_voicemail_notification(
    self,
    uuid_val: str,
    username: str,
    domain: str,
    file_path: str,
    cid_name: str,
    cid_number: str,
    message_len: int,
):
    """Send a voicemail email notification with optional audio attachment.

    Called with a 10-second countdown from the ingest view so FreeSWITCH
    has time to finish writing the WAV file before we try to attach it.
    """
    from .models import Voicemail  # noqa: PLC0415
    from django.core.mail import EmailMessage  # noqa: PLC0415

    # username is the voicemail UUID — look up by PK
    vm = Voicemail.objects.filter(voicemail_uuid=username).first()

    if not vm or not vm.voicemail_mail_to or vm.voicemail_on_new_message not in ('email', 'both'):
        return

    try:
        from .models import VoicemailTranscript  # noqa: PLC0415
        transcript_text = ''
        try:
            t = VoicemailTranscript.objects.filter(
                message_uuid=uuid_val, status=VoicemailTranscript.STATUS_DONE
            ).first()
            if t and t.transcript:
                transcript_text = t.transcript
        except Exception:
            pass

        subject = f'New voicemail from {cid_name or cid_number or "unknown"} for {vm.voicemail_id}'
        body = (
            f'You have a new voicemail message.\n\n'
            f'From: {cid_name} <{cid_number}>\n'
            f'Duration: {message_len} seconds\n'
        )
        if transcript_text:
            body += f'\nTranscript:\n{transcript_text}\n'
        email = EmailMessage(
            subject=subject,
            body=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=_split_emails(vm.voicemail_mail_to),
        )
        if vm.voicemail_file == 'attach':
            if os.path.isfile(file_path):
                with open(file_path, 'rb') as f:
                    email.attach(os.path.basename(file_path), f.read(), 'audio/wav')
                logger.debug('send_voicemail_notification: attaching %s', file_path)
            else:
                logger.warning('send_voicemail_notification: file not ready yet, retrying: %s', file_path)
                raise self.retry(countdown=20)

        email.send(fail_silently=False)
        logger.info('send_voicemail_notification: sent to %s for %s', vm.voicemail_mail_to, uuid_val)
    except Exception as exc:
        logger.error('send_voicemail_notification: failed for %s: %s', uuid_val, exc)
        raise self.retry(exc=exc)


@shared_task
def purge_deleted_messages(domain_uuid: str = None):
    """Permanently delete VoicemailMessage rows with status 'deleted'.

    Intended to be run as a periodic Celery Beat task.  Optionally scoped to
    a single domain.
    """
    from .models import VoicemailMessage  # noqa: PLC0415

    qs = VoicemailMessage.objects.filter(message_status='deleted')
    if domain_uuid:
        qs = qs.filter(domain_id=domain_uuid)
    count, _ = qs.delete()
    logger.info('purge_deleted_messages: removed %d messages (domain=%s)', count, domain_uuid)
    return count
