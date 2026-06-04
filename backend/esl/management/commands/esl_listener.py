# gevent monkey-patching must happen before any other imports
import gevent.monkey
gevent.monkey.patch_all()

"""
Management command: esl_listener

Maintains a persistent FreeSWITCH ESL inbound connection, subscribes to
CHANNEL_CREATE / CHANNEL_ANSWER / CHANNEL_HANGUP events, and fires a
call.incoming webhook on CHANNEL_CREATE to all active tenant API keys.

Offline extension handling
--------------------------
When CHANNEL_CREATE arrives for an extension that is not registered:
  1. A call.incoming webhook fires immediately.
  2. A background thread polls sofia_contact() every second for up to
     offline_poll_timeout seconds (default 30).
  3a. Extension registers → uuid_bridge issued, call rings normally.
  3b. Timeout → uuid_transfer to forward_user_not_registered_destination,
      or hangup with USER_NOT_REGISTERED.

Run as a dedicated systemd service. Auto-reconnects on disconnect.
"""
import datetime
import hashlib
import hmac
import json
import logging
import time
import urllib.request
import uuid
from concurrent.futures import ThreadPoolExecutor

import gevent
import greenswitch
import psycopg2
from django.conf import settings
from django.core.management.base import BaseCommand

logger = logging.getLogger('esl.listener')

RECONNECT_DELAY = 5   # seconds between reconnection attempts
POLL_INTERVAL = 1     # seconds between offline-extension poll attempts

# Thread pool — webhook delivery + offline poll loops run here
_executor = ThreadPoolExecutor(max_workers=40, thread_name_prefix='esl-worker')

SUBSCRIBE_EVENTS = ['CHANNEL_CREATE', 'CHANNEL_OUTGOING', 'CHANNEL_ANSWER', 'CHANNEL_HANGUP', 'CHANNEL_PARK', 'PLAYBACK_STOP', 'CUSTOM']

# Active ESL connection — set by run_listener(), used by _esl_api()
_esl_conn = None

# ── In-memory tenant/DID cache ────────────────────────────────────────────────
# Loaded via raw psycopg2 at startup to avoid Django thread-local DB conflicts
# with gevent. All values are plain dicts (no ORM objects).

_tenant_by_code   = {}  # tenant_code  → tenant dict
_tenant_by_domain = {}  # domain_name  → tenant dict
_tenant_by_did    = {}  # E.164 / 10-digit DID → tenant dict


def _psycopg2_connect():
    """Open a raw psycopg2 connection using Django's default DB config."""
    db = settings.DATABASES['default']
    return psycopg2.connect(
        dbname=db['NAME'], user=db['USER'], password=db['PASSWORD'],
        host=db['HOST'], port=db['PORT'],
        options='-c search_path=public',
    )


def _load_tenant_cache():
    """Populate in-memory tenant/domain/DID lookup tables."""
    global _tenant_by_code, _tenant_by_domain, _tenant_by_did

    conn = _psycopg2_connect()
    try:
        cur = conn.cursor()

        cur.execute(
            "SELECT tenant_uuid, tenant_code, tenant_name "
            "FROM v_tenants WHERE tenant_enabled = true"
        )
        tenants = {}
        for tenant_uuid, tenant_code, tenant_name in cur.fetchall():
            t = {'tenant_uuid': str(tenant_uuid), 'tenant_code': tenant_code, 'tenant_name': tenant_name}
            tenants[str(tenant_uuid)] = t
            _tenant_by_code[tenant_code] = t

        cur.execute(
            "SELECT domain_name, tenant_uuid FROM v_domains "
            "WHERE domain_enabled = true AND tenant_uuid IS NOT NULL"
        )
        for domain_name, tenant_uuid in cur.fetchall():
            tenant = tenants.get(str(tenant_uuid))
            if tenant:
                _tenant_by_domain[domain_name] = tenant

        cur.execute(
            "SELECT destination_number, tenant_uuid FROM v_destinations "
            "WHERE tenant_uuid IS NOT NULL"
        )
        for number, tenant_uuid in cur.fetchall():
            tenant = tenants.get(str(tenant_uuid))
            if not tenant:
                continue
            _tenant_by_did[number] = tenant
            # Index both E.164 (+1XXXXXXXXXX) and 10-digit forms
            if number.startswith('+1') and len(number) == 12:
                _tenant_by_did[number[2:]] = tenant
            elif not number.startswith('+') and len(number) == 10:
                _tenant_by_did['+1' + number] = tenant

        cur.close()
    finally:
        conn.close()

    logger.info(
        'Tenant cache loaded: %d tenants, %d domains, %d DIDs',
        len(_tenant_by_code), len(_tenant_by_domain), len(_tenant_by_did),
    )


# ── Tenant / extension resolution ─────────────────────────────────────────────

def _resolve_tenant(headers: dict):
    """
    Resolve tenant from in-memory cache (no DB queries).

    Strategy 1: Caller-Username suffix — e.g. "1001-IHS" → code "IHS"
    Strategy 2: variable_domain_name header
    Strategy 3: Caller-Destination-Number matched against DID cache
    """
    username = headers.get('Caller-Username', '')
    if username and '-' in username:
        code = username.rsplit('-', 1)[-1]
        tenant = _tenant_by_code.get(code)
        if tenant:
            return tenant

    domain = headers.get('variable_domain_name', '')
    if domain:
        tenant = _tenant_by_domain.get(domain)
        if tenant:
            return tenant

    dest = headers.get('Caller-Destination-Number', '')
    if dest:
        tenant = _tenant_by_did.get(dest)
        if tenant:
            return tenant

    return None


def _db_query(fn, *args, **kwargs):
    """Run a Django ORM callable in a real OS thread to avoid gevent thread-local issues."""
    import gevent
    return gevent.get_hub().threadpool.spawn(fn, *args, **kwargs).get()


def _resolve_extension(headers: dict):
    """Return the Extension ORM object for the dialled number, or None."""
    dest = headers.get('Caller-Destination-Number', '')
    domain = (
        headers.get('variable_domain_name', '')
        or headers.get('variable_sip_to_host', '')
    )
    if not dest or not domain:
        return None

    def _lookup(dest, domain):
        from django.db import close_old_connections
        close_old_connections()
        from apps.extensions.models import Extension
        from apps.destinations.models import Destination
        try:
            return Extension.objects.select_related('tenant').get(
                extension=dest, domain__domain_name=domain, enabled=True,
            )
        except Exception:
            pass
        bare = dest.lstrip('+').lstrip('1')
        did = Destination.objects.filter(
            destination_number__iregex=r'^(\+?1?)' + bare + r'$',
            destination_enabled=True,
            dest_type='extension',
        ).first()
        logger.debug('_resolve_extension DID lookup: dest=%s bare=%s did=%s target=%s',
                     dest, bare, did, did.dest_target_uuid if did else None)
        if did and did.dest_target_uuid:
            try:
                return Extension.objects.select_related('tenant').get(
                    extension_uuid=did.dest_target_uuid, enabled=True,
                )
            except Exception:
                pass
        return None

    try:
        return _db_query(_lookup, dest, domain)
    except Exception as e:
        logger.debug('_resolve_extension exception: %s', e)
        return None


def _is_fax_destination(dest: str) -> bool:
    """Return True if the destination number is a fax-only DID."""
    if not dest:
        return False

    def _lookup(dest):
        from django.db import close_old_connections
        close_old_connections()
        from apps.destinations.models import Destination
        bare = dest.lstrip('+').lstrip('1')
        return Destination.objects.filter(
            destination_number__iregex=r'^(\+?1?)' + bare + r'$',
            destination_enabled=True,
            dest_type='fax',
        ).exists()

    try:
        return _db_query(_lookup, dest)
    except Exception:
        return False


# ── Affinity capture (live, on extension dial-out) ────────────────────────────

import re as _re


def _normalize_customer(num: str) -> str:
    """Strip non-digits, drop leading US '1', keep last 10. Returns '' if too short."""
    if not num:
        return ''
    digits = _re.sub(r'\D', '', str(num))
    if len(digits) > 10 and digits.startswith('1'):
        digits = digits[1:]
    return digits[-10:] if len(digits) >= 10 else ''


def _extract_internal_ext(caller_username: str, tenant_code: str) -> str:
    """
    Pull the internal extension number from a tenant-suffixed username.
    "901-IHDT" + tenant_code "IHDT" → "901". Returns '' if it doesn't match.
    """
    if not caller_username or not tenant_code:
        return ''
    suffix = f'-{tenant_code}'
    if caller_username.endswith(suffix):
        head = caller_username[: -len(suffix)]
        if head.isdigit():
            return head
    if caller_username.isdigit():
        return caller_username
    return ''


def _upsert_affinity_live(tenant_uuid: str, domain_uuid, caller_number: str,
                          extension_number: str, when_ts):
    """
    Last-write-wins upsert into v_caller_extension_affinity using raw psycopg2
    (avoids Django ORM thread-locals under gevent).
    """
    try:
        conn = _psycopg2_connect()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO v_caller_extension_affinity "
            "  (affinity_uuid, tenant_uuid, domain_uuid, caller_number, "
            "   extension_number, last_seen, source, insert_date, update_date) "
            "VALUES (gen_random_uuid(), %s, %s, %s, %s, %s, 'live_outbound', NOW(), NOW()) "
            "ON CONFLICT ON CONSTRAINT uniq_affinity_tenant_caller DO UPDATE SET "
            "  extension_number = EXCLUDED.extension_number, "
            "  last_seen        = EXCLUDED.last_seen, "
            "  source           = 'live_outbound', "
            "  update_date      = NOW(), "
            "  domain_uuid      = COALESCE(v_caller_extension_affinity.domain_uuid, EXCLUDED.domain_uuid)",
            (tenant_uuid, domain_uuid, caller_number, extension_number, when_ts),
        )
        conn.commit()
        cur.close()
        conn.close()
        logger.info(
            '[affinity] live upsert tenant=%s ext=%s customer=%s',
            tenant_uuid, extension_number, caller_number,
        )
    except Exception as exc:
        logger.error('[affinity] upsert failed: %s', exc)


def _maybe_capture_outbound_affinity(headers: dict, tenant: dict):
    """
    On CHANNEL_OUTGOING (B-leg created when extension dials out), record
    (tenant, customer_number) → extension_number. This is the live signal —
    no CDR involved.
    """
    caller_username = headers.get('Caller-Username', '')
    tenant_code = tenant.get('tenant_code', '')
    ext = _extract_internal_ext(caller_username, tenant_code)
    if not ext:
        return

    customer_raw = (
        headers.get('Caller-Destination-Number', '')
        or headers.get('variable_dialed_extension', '')
    )
    customer = _normalize_customer(customer_raw)
    if not customer:
        return

    # Skip internal-to-internal dials (extension calling another extension).
    # Internal targets are short (3-5 digits) and never normalize to 10.
    if customer_raw and customer_raw.isdigit() and len(customer_raw) < 7:
        return

    when_ts = datetime.datetime.now(datetime.timezone.utc)
    domain_uuid = headers.get('variable_domain_uuid') or None

    _executor.submit(
        _upsert_affinity_live,
        tenant['tenant_uuid'], domain_uuid, customer, ext, when_ts,
    )


# ── ESL helpers ───────────────────────────────────────────────────────────────

def _esl_api(command: str) -> str:
    """Send a synchronous ESL API command on the shared connection."""
    if _esl_conn is None:
        raise RuntimeError('No ESL connection')
    resp = _esl_conn.send(f'api {command}\n\n')
    return resp.data if hasattr(resp, 'data') else str(resp)


def _is_registered(sip_id: str, domain_name: str) -> bool:
    try:
        result = _esl_api(f'sofia_contact */{sip_id}@{domain_name}')
        return bool(result) and not result.strip().startswith('error')
    except Exception:
        return False


def _is_call_active(call_uuid: str) -> bool:
    try:
        return _esl_api(f'uuid_exists {call_uuid}').strip().lower() == 'true'
    except Exception:
        return False


# ── Payload builder ───────────────────────────────────────────────────────────

def _build_call_payload(event_name: str, headers: dict, extra: dict = None) -> dict:
    payload = {
        'event': f'call.{event_name.lower()}',
        'call_uuid': headers.get('Unique-ID', ''),
        'caller_id_name': headers.get('Caller-Caller-ID-Name', ''),
        'caller_id_number': headers.get('Caller-Caller-ID-Number', ''),
        'destination_number': headers.get('Caller-Destination-Number', ''),
        'caller_username': headers.get('Caller-Username', ''),
        'direction': headers.get('Call-Direction', ''),
        'timestamp': headers.get('Event-Date-Timestamp', ''),
        'state': headers.get('Channel-Call-State', ''),
    }
    if extra:
        payload.update(extra)
    return payload


# ── Webhook delivery ──────────────────────────────────────────────────────────

def _fire_webhooks(tenant: dict, payload: dict):
    """
    Fetch API keys with a webhook_url for this tenant via raw SQL, then submit
    one delivery task per key to the thread pool.
    """
    try:
        conn = _psycopg2_connect()
        cur = conn.cursor()
        cur.execute(
            "SELECT id, webhook_url, webhook_secret "
            "FROM v_tenant_api_keys "
            "WHERE tenant_id = %s AND is_active = true AND webhook_url != ''",
            (tenant['tenant_uuid'],),
        )
        rows = cur.fetchall()
        cur.close()
        conn.close()
    except Exception as exc:
        logger.error('_fire_webhooks: DB error fetching API keys: %s', exc)
        return

    payload_bytes = json.dumps(payload, default=str).encode('utf-8')
    for key_id, webhook_url, webhook_secret in rows:
        _executor.submit(_deliver_webhook, key_id, webhook_url, webhook_secret, payload, payload_bytes)


def _deliver_webhook(key_id, webhook_url: str, webhook_secret: str, payload: dict, payload_bytes: bytes):
    """POST one webhook and audit-log the delivery via raw psycopg2."""
    http_headers = {
        'Content-Type': 'application/json',
        'User-Agent': 'IHSPBX-Webhook/1.0',
    }
    if webhook_secret:
        sig = hmac.new(webhook_secret.encode(), payload_bytes, hashlib.sha256).hexdigest()
        http_headers['X-Signature'] = sig

    status_code = None
    error = ''
    success = False
    delivered_at = None
    try:
        req = urllib.request.Request(webhook_url, data=payload_bytes, headers=http_headers, method='POST')
        with urllib.request.urlopen(req, timeout=10) as resp:
            status_code = resp.status
            success = status_code < 300
            delivered_at = datetime.datetime.now(datetime.timezone.utc) if success else None
            if success:
                logger.info('Webhook delivered → %s (%d)', webhook_url, status_code)
            else:
                error = f'HTTP {status_code}'
                logger.warning('Webhook failed → %s (%d)', webhook_url, status_code)
    except Exception as exc:
        error = str(exc)
        logger.error('Webhook error → %s: %s', webhook_url, exc)

    try:
        conn = _psycopg2_connect()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO v_webhook_deliveries "
            "    (id, api_key_id, event, payload, status, attempts, last_response_code, last_error, delivered_at, created_at) "
            "VALUES (%s, %s, %s, %s, %s, 1, %s, %s, %s, NOW())",
            (
                str(uuid.uuid4()),
                key_id,
                payload.get('event', ''),
                json.dumps(payload, default=str),
                'success' if success else 'failed',
                status_code,
                error,
                delivered_at,
            ),
        )
        conn.commit()
        cur.close()
        conn.close()
    except Exception as exc:
        logger.error('_deliver_webhook: failed to log delivery: %s', exc)


# ── Offline extension poll-and-transfer ───────────────────────────────────────

def _poll_and_transfer(call_uuid: str, sip_id: str, domain_name: str,
                       extension, timeout: int, forwarding_dest: str, tenant_code: str = ''):
    """
    Poll sofia_contact every POLL_INTERVAL seconds for up to `timeout` seconds.
    - Extension registers → uuid_bridge to the SIP contact.
    - Caller hangs up during poll → exit cleanly.
    - Timeout → transfer to forwarding_dest or hangup USER_NOT_REGISTERED.
    """
    deadline = time.time() + timeout
    logger.info('Polling for %s@%s (call %s, timeout=%ds)', sip_id, domain_name, call_uuid, timeout)

    while time.time() < deadline:
        if not _is_call_active(call_uuid):
            logger.info('Call %s ended during offline poll — aborting', call_uuid)
            return

        if _is_registered(sip_id, domain_name):
            logger.info('Extension %s came online — transferring call %s to extension', sip_id, call_uuid)
            try:
                _esl_api(f'uuid_transfer {call_uuid} {sip_id} XML default-{tenant_code}')
            except Exception as exc:
                logger.error('uuid_transfer failed for %s to %s: %s', call_uuid, sip_id, exc)
            return

        time.sleep(POLL_INTERVAL)

    if not _is_call_active(call_uuid):
        return

    if forwarding_dest:
        logger.info('Timeout for %s — transferring call %s to %s', sip_id, call_uuid, forwarding_dest)
        try:
            if forwarding_dest.startswith('voicemail:'):
                vm_ext = forwarding_dest.split(':', 1)[1]
                _esl_api(f'uuid_transfer {call_uuid} {vm_ext} XML default-{tenant_code}')
            else:
                _esl_api(f'uuid_transfer {call_uuid} {forwarding_dest} XML default-{tenant_code}')
        except Exception as exc:
            logger.error('Forwarding transfer failed for %s: %s', call_uuid, exc)
    else:
        logger.info('Timeout for %s — hanging up call %s', sip_id, call_uuid)
        try:
            _esl_api(f'uuid_kill {call_uuid} USER_NOT_REGISTERED')
        except Exception as exc:
            logger.error('uuid_kill failed for %s: %s', call_uuid, exc)


# ── Parked-call presence fix ──────────────────────────────────────────────────

def _fix_park_presence(headers: dict):
    """
    Fire a PRESENCE_IN ESL event to override the hardcoded display="park" that
    mod_valet_parking puts in dialog-info NOTIFYs.  Must run after the channel
    is parked so mod_sofia picks up the corrected name/number.
    """
    presence_id = headers.get('variable_presence_id', '')
    if not presence_id:
        return

    caller_name   = (
        headers.get('variable_effective_caller_id_name', '')
        or headers.get('Caller-Caller-ID-Name', '')
    )
    caller_number = (
        headers.get('variable_effective_caller_id_number', '')
        or headers.get('Caller-Caller-ID-Number', '')
    )
    if not caller_name and not caller_number:
        return

    # PRESENCE_IN event body that mod_sofia uses to rebuild dialog-info XML
    event_body = (
        f'Event-Name: PRESENCE_IN\n'
        f'proto: sip\n'
        f'login: {presence_id}\n'
        f'from: {presence_id}\n'
        f'status: Active\n'
        f'rpid: active\n'
        f'answer-state: confirmed\n'
        f'caller-id-name: {caller_name}\n'
        f'caller-id-number: {caller_number}\n'
        f'unique-id: {headers.get("Unique-ID", "")}\n'
    )
    try:
        _esl_conn.send(f'sendevent PRESENCE_IN\n{event_body}\n')
        logger.info(
            'PRESENCE_IN fired for parked channel %s presence_id=%s name=%s number=%s',
            headers.get('Unique-ID', ''), presence_id, caller_name, caller_number,
        )
    except Exception as exc:
        logger.error('Failed to fire PRESENCE_IN for parked channel: %s', exc)


def _is_mobile_agent(agent: str) -> bool:
    if not agent:
        return False
    agent_lower = agent.lower()
    return any(keyword in agent_lower for keyword in ['linphone', 'ihs', 'mobile', 'ios', 'android', 'uc-'])


def _get_registered_agents(sip_id: str, domain_name: str) -> list:
    """Return a list of user-agents for all active registrations of this SIP ID."""
    agents = []
    import re
    # Check every enabled profile — WebRTC devices register on the 'webrtc'
    # profile, not 'internal', so a hardcoded profile would miss them.
    try:
        from apps.sip_profiles.models import SipProfile
        profiles = list(
            SipProfile.objects.filter(sip_profile_enabled=True)
            .values_list('sip_profile_name', flat=True)
        )
    except Exception:
        profiles = []
    for default_profile in ('internal', 'external', 'webrtc'):
        if default_profile not in profiles:
            profiles.append(default_profile)
    for profile in profiles:
        try:
            raw = _esl_api(f'sofia status profile {profile} reg')
            if not raw or 'Invalid Profile' in raw:
                continue
            for block in re.split(r'\n(?=Call-ID:)', raw):
                if f'User: {sip_id}@{domain_name}' in block or f'User: {sip_id}@' in block:
                    for line in block.splitlines():
                        if line.strip().startswith('Agent:'):
                            agents.append(line.split(':', 1)[1].strip())
        except Exception as exc:
            logger.error('Failed to parse registered agents for profile %s: %s', profile, exc)
    return agents


def _trigger_re_transfer(sip_id: str, domain_name: str):
    try:
        raw_channels = _esl_api('show channels as json')
        if not raw_channels or 'rows' not in raw_channels:
            return
        import json
        data = json.loads(raw_channels)
        rows = data.get('rows', [])
        for row in rows:
            dest = row.get('dest', '')
            # We want to find inbound calls that are currently ringing or routing to this extension
            if dest == sip_id and row.get('direction') == 'inbound' and row.get('answerstate') == 'ringing':
                call_uuid = row.get('uuid')
                tenant = _tenant_by_domain.get(domain_name)
                tenant_code = tenant['tenant_code'] if tenant else ''
                logger.info('Active ringing call found for %s (uuid: %s). Re-transferring to include mobile.', sip_id, call_uuid)
                _esl_api(f'uuid_transfer {call_uuid} {sip_id} XML default-{tenant_code}')
    except Exception as exc:
        logger.error('Failed to trigger re-transfer on mobile registration: %s', exc)


# ── Event handler ─────────────────────────────────────────────────────────────

def _handle_event(event):
    """Called by greenswitch for every subscribed ESL event."""
    try:
        headers = event.headers
        event_name = headers.get('Event-Name', '')
        if event_name not in SUBSCRIBE_EVENTS:
            return

        if event_name == 'CUSTOM':
            subclass = headers.get('Event-Subclass', '')
            if subclass == 'sofia::register':
                sip_id = headers.get('username')
                domain_name = headers.get('realm')
                user_agent = headers.get('user-agent', '')
                if sip_id and domain_name and _is_mobile_agent(user_agent):
                    logger.info('Mobile registration detected: %s@%s (%s)', sip_id, domain_name, user_agent)
                    _trigger_re_transfer(sip_id, domain_name)
            return

        tenant = _resolve_tenant(headers)
        if tenant is None:
            logger.debug('No tenant for %s uuid=%s', event_name, headers.get('Unique-ID'))
            return

        call_uuid = headers.get('Unique-ID', '')
        payload = _build_call_payload(event_name, headers, {
            'tenant_code': tenant['tenant_code'],
            'tenant_id': tenant['tenant_uuid'],
        })

        logger.info(
            'ESL %s | tenant=%s | uuid=%s | %s → %s',
            event_name, tenant['tenant_code'], call_uuid,
            payload['caller_id_number'], payload['destination_number'],
        )

        if event_name == 'CHANNEL_PARK':
            _fix_park_presence(headers)
            return

        # Live affinity capture: extension dialed out → record (customer → ext).
        # CHANNEL_OUTGOING fires on the B-leg the moment FreeSWITCH originates
        # the carrier-side call, regardless of whether the customer answers.
        if event_name == 'CHANNEL_OUTGOING':
            _maybe_capture_outbound_affinity(headers, tenant)
            return

# ── Handle Answer / Hangup Webhooks ──────────────────────────────────
        if event_name in ('CHANNEL_ANSWER', 'CHANNEL_HANGUP'):

            # Skip B-legs / outbound channels / bridged legs
            if (
                headers.get('variable_is_outbound_channel') == 'true'
                or headers.get('variable_originator_uuid')
                or headers.get('Other-Leg-Unique-ID')
            ):
                logger.debug(
                    'Skipping %s for B-leg/outbound channel uuid=%s',
                    event_name,
                    call_uuid,
                )
                return

            # Auto-start AI audio stream for extension 999
            if event_name == 'CHANNEL_ANSWER':
                dest = headers.get('Caller-Destination-Number', '')
                if dest in ('999', '999-IHS'):
                    ai_ws_base = getattr(settings, 'AI_BRIDGE_WS', 'ws://127.0.0.1:5001/audio')
                    ai_ws = f'{ai_ws_base}/{call_uuid}'
                    try:
                        result = _esl_api(f'uuid_audio_stream {call_uuid} start {ai_ws} mono 8000')
                        logger.info('AI audio stream started for call %s → %s', call_uuid, ai_ws)
                    except Exception as exc:
                        logger.error('Failed to start AI audio stream for %s: %s', call_uuid, exc)

            # Restart AI audio stream after Gemini response playback finishes
            if event_name == 'PLAYBACK_STOP':
                app_file = headers.get('Application-File', '')
                logger.debug('PLAYBACK_STOP Application-File: %s uuid=%s', app_file, call_uuid)
                if 'gemini_' in app_file:
                    ai_ws_base = getattr(settings, 'AI_BRIDGE_WS', 'ws://127.0.0.1:5001/audio')
                    ai_ws = f'{ai_ws_base}/{call_uuid}'
                    def _restart_stream(uuid, ws):
                        for attempt in range(3):
                            time.sleep(0.5 * (attempt + 1))
                            try:
                                result = _esl_api(f'uuid_audio_stream {uuid} start {ws} mono 8000')
                                logger.info('AI stream restarted for %s attempt=%d result=%s', uuid, attempt + 1, result)
                                if '+OK' in result:
                                    break
                            except Exception as exc:
                                logger.error('AI stream restart error %s attempt=%d: %s', uuid, attempt + 1, exc)
                    _executor.submit(_restart_stream, call_uuid, ai_ws)

            event_type = 'answered' if event_name == 'CHANNEL_ANSWER' else 'ended'

            tenant_code = tenant.get('tenant_code', '')

            ext_number = headers.get('Caller-Destination-Number', '')

            # Skip invalid extension values
            if not ext_number or not ext_number.isdigit():
                logger.debug(
                    'Skipping %s webhook — invalid extension %s uuid=%s',
                    event_type,
                    ext_number,
                    call_uuid,
                )
                return

            payload['event'] = f'call.{event_type}'
            payload['extension'] = f'{ext_number}-{tenant_code}'

            _fire_webhooks(tenant, payload)

            logger.info(
                'Fired call.%s webhook for extension %s uuid=%s',
                event_type,
                payload['extension'],
                call_uuid,
            )

            return

        if event_name != 'CHANNEL_CREATE':
            return

        if payload.get('direction') != 'inbound':
            logger.debug('Skipping call.incoming webhook for non-inbound channel uuid=%s direction=%s', call_uuid, payload.get('direction'))
            return

        # Skip outbound legs — when we bridge to an extension, the new leg is outbound.
        # This prevents duplicate call.incoming webhooks for the same call.
        if headers.get('variable_is_outbound_channel') == 'true' or headers.get('variable_originator_uuid'):
            logger.debug('Skipping call.incoming webhook for outbound leg or sub-channel uuid=%s', call_uuid)
            return

        # Any channel where the caller is a tenant-suffixed internal extension
        # (e.g. "908-IHDT", "929-IHDT") is either an outbound call or an internal
        # transfer/forward leg — never a true inbound call from PSTN. Skip it.
        caller_username = headers.get('Caller-Username', '')
        dest = headers.get('Caller-Destination-Number', '')
        tenant_code = tenant.get('tenant_code', '')
        caller_is_internal = bool(caller_username and tenant_code and caller_username.endswith(f'-{tenant_code}'))
        if caller_is_internal:
            logger.debug('Skipping call.incoming webhook — internal caller %s to %s uuid=%s', caller_username, dest, call_uuid)
            return

        # Skip fax DIDs — they fire call.incoming but are not voice calls
        if _is_fax_destination(dest):
            logger.debug('Skipping call.incoming webhook — fax destination %s uuid=%s', dest, call_uuid)
            return

        extension = _resolve_extension(headers)
        domain_name = (
            headers.get('variable_domain_name', '')
            or headers.get('variable_sip_to_host', '')
        )
        tenant_code = tenant.get('tenant_code', '')
        ext_number = extension.extension if extension else payload['destination_number']
        payload['event'] = 'call.incoming'
        payload['extension'] = f'{ext_number}-{tenant_code}' if tenant_code else ext_number

        _fire_webhooks(tenant, payload)
        logger.info('Fired call.incoming webhook for extension %s', payload['extension'])

        if not (extension and domain_name):
            return

        sip_id = extension.sip_username or extension.extension
        if _is_registered(sip_id, domain_name):
            # If registered, we check if a mobile app is registered.
            # If not, we still fire the push notification webhook to wake the mobile app up!
            registered_agents = _get_registered_agents(sip_id, domain_name)
            has_mobile = any(_is_mobile_agent(agent) for agent in registered_agents)
            if not has_mobile and (getattr(extension, 'mobile_push_enabled', False) or tenant.get('push_notifications_enabled', False)):
                logger.info('Extension %s registered on desk phone, but mobile is offline. Dispatching push wake-up.', sip_id)
                # Fire webhook so the push notification server can wake the mobile app
                payload['event'] = 'call.incoming'
                payload['extension'] = f'{ext_number}-{tenant_code}' if tenant_code else ext_number
                _fire_webhooks(tenant, payload)
            return

        offline_poll_timeout = tenant.get('offline_poll_timeout', 30)
        logger.info('Extension %s offline — polling for call %s (timeout=%ds)', sip_id, call_uuid, offline_poll_timeout)

        try:
            _esl_api(f'uuid_ring_ready {call_uuid}')
        except Exception as exc:
            logger.error('uuid_ring_ready failed for %s: %s', call_uuid, exc)

        forwarding_dest = ''
        if (
            extension.call_forward_active
            and extension.forward_user_not_registered_enabled
            and extension.forward_user_not_registered_destination
        ):
            forwarding_dest = extension.forward_user_not_registered_destination

        _executor.submit(
            _poll_and_transfer,
            call_uuid, sip_id, domain_name, extension,
            offline_poll_timeout, forwarding_dest, tenant['tenant_code'],
        )

    except Exception as exc:
        logger.error('Error handling ESL event: %s', exc, exc_info=True)


# ── ESL connection ─────────────────────────────────────────────────────────────

def run_listener():
    """Open a persistent ESL inbound connection and block until it drops."""
    global _esl_conn

    _load_tenant_cache()
    logger.info('Connecting to FreeSWITCH ESL at %s:%s …', settings.FREESWITCH_HOST, settings.FREESWITCH_PORT)

    conn = greenswitch.InboundESL(
        host=settings.FREESWITCH_HOST,
        port=settings.FREESWITCH_PORT,
        password=settings.FREESWITCH_PASSWORD,
    )
    conn.connect()
    _esl_conn = conn
    logger.info('ESL connected. Subscribing to: %s', ', '.join(SUBSCRIBE_EVENTS))

    conn.send('event plain ' + ' '.join(SUBSCRIBE_EVENTS))
    for event_name in SUBSCRIBE_EVENTS:
        conn.register_handle(event_name, _handle_event)

    logger.info('ESL listener running.')
    gevent.joinall([conn._receive_events_greenlet, conn._process_events_greenlet])
    _esl_conn = None


class Command(BaseCommand):
    help = 'Run the persistent FreeSWITCH ESL event listener for incoming call webhooks.'

    def handle(self, *args, **options):
        self.stdout.write('Starting ESL listener (Ctrl+C to stop)…')
        while True:
            try:
                run_listener()
                logger.warning('ESL connection closed. Reconnecting in %ds…', RECONNECT_DELAY)
            except KeyboardInterrupt:
                self.stdout.write('ESL listener stopped.')
                break
            except Exception as exc:
                logger.error('ESL listener error: %s — reconnecting in %ds', exc, RECONNECT_DELAY)
            time.sleep(RECONNECT_DELAY)
