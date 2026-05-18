"""
Celery tasks for FreeSWITCH ESL operations.
These run in background workers and also drive the event listener loop.
"""
import json
import logging
from celery import shared_task
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
import time
import json
from django.db import connections
try:
    import psutil
    PSUTIL_AVAILABLE = True
except Exception:
    PSUTIL_AVAILABLE = False

logger = logging.getLogger('esl')
channel_layer = get_channel_layer()


@shared_task(bind=True, max_retries=3, default_retry_delay=5)
def reload_xml(self):
    """Reload FreeSWITCH XML configuration."""
    try:
        from .client import get_esl_client
        esl = get_esl_client()
        result = esl.reload_xml()
        logger.info(f"reloadxml result: {result}")
        return result
    except Exception as exc:
        logger.error(f"reload_xml task failed: {exc}")
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=5)
def sofia_profile_reload(self, profile='external'):
    """Reload (restart) a Sofia SIP profile — use only when gateways won't load via rescan."""
    try:
        from .client import get_esl_client
        esl = get_esl_client()
        result = esl.sofia_reload(profile)
        logger.info(f"sofia reload {profile}: {result}")
        return result
    except Exception as exc:
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=5)
def sofia_profile_rescan(self, profile='external'):
    """Rescan a Sofia SIP profile for new/changed gateways (non-disruptive, no call drops)."""
    try:
        from .client import get_esl_client
        esl = get_esl_client()
        result = esl.sofia_rescan(profile)
        logger.info(f"sofia rescan {profile}: {result}")
        return result
    except Exception as exc:
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=5)
def sofia_killgw_and_rescan(self, gateway_name, profile='external'):
    """Kill an existing gateway then rescan so updated config takes effect."""
    try:
        from .client import get_esl_client
        esl = get_esl_client()
        esl.gateway_killgw(gateway_name, profile)
        result = esl.sofia_rescan(profile)
        logger.info(f"killgw {gateway_name} + rescan {profile}: {result}")
        return result
    except Exception as exc:
        raise self.retry(exc=exc)


@shared_task
def originate_call(
    src,
    dst,
    dialplan='XML',
    context='default',
    caller_id_name='',
    caller_id_number='',
):
    """Originate a call (click-to-call)."""
    from .client import get_esl_client
    esl = get_esl_client()
    return esl.originate(src, dst, dialplan, context, caller_id_name, caller_id_number)


@shared_task
def hangup_call(uuid, cause='NORMAL_CLEARING'):
    """Hangup a call by channel UUID."""
    from .client import get_esl_client
    esl = get_esl_client()
    return esl.hangup(uuid, cause)


@shared_task
def push_active_calls_update():
    """Fetch current active calls and broadcast to WebSocket consumers."""
    try:
        from .client import get_esl_client
        from .views import _normalize_json_rows
        esl = get_esl_client()
        raw = esl.show_calls()
        rows = _normalize_json_rows(raw)
        calls = [
            {
                'uuid':     row.get('uuid', ''),
                'cid_name': row.get('cid_name', ''),
                'cid_num':  row.get('cid_num', ''),
                'dest':     row.get('dest', ''),
                'state':    row.get('callstate') or row.get('state', ''),
                'answered': row.get('callstate') == 'ACTIVE',
                'duration': row.get('elapsed_time', 0),
            }
            for row in rows
        ]
        async_to_sync(channel_layer.group_send)(
            'active_calls',
            {'type': 'call_event', 'event_type': 'snapshot', 'data': calls},
        )
    except Exception as e:
        logger.error(f"push_active_calls_update error: {e}")


@shared_task
def push_registrations_update():
    """Fetch current registrations and broadcast to WebSocket consumers."""
    try:
        from .client import get_esl_client
        esl = get_esl_client()
        raw = esl.show_registrations()
        rows = json.loads(raw).get('rows', []) if isinstance(raw, str) else raw.get('rows', [])
        async_to_sync(channel_layer.group_send)(
            'registrations',
            {'type': 'registration_event', 'event_type': 'snapshot', 'data': rows},
        )
    except Exception as e:
        logger.error(f"push_registrations_update error: {e}")


@shared_task
def push_system_metrics_update():
    """Collect basic system metrics and broadcast them."""
    try:
        if not PSUTIL_AVAILABLE:
            logger.error("psutil not installed; cannot collect system metrics")
            return
        metrics = {
            'cpu_percent': psutil.cpu_percent(interval=1),
            'memory': psutil.virtual_memory()._asdict(),
            'disk': {p.mountpoint: psutil.disk_usage(p.mountpoint)._asdict() for p in psutil.disk_partitions(all=False)},
            'load_avg': getattr(psutil, 'getloadavg', lambda: (0, 0, 0))(),
            'timestamp': int(time.time()),
        }
        async_to_sync(channel_layer.group_send)(
            'system_metrics',
            {'type': 'system_metrics_event', 'event_type': 'snapshot', 'data': metrics},
        )
    except Exception as e:
        logger.error(f"push_system_metrics_update error: {e}")


@shared_task
def push_freeswitch_status_update():
    """Fetch FreeSWITCH status and broadcast it."""
    try:
        from .client import get_esl_client
        esl = get_esl_client()
        status = esl.fs_status()
        async_to_sync(channel_layer.group_send)(
            'freeswitch_status',
            {'type': 'freeswitch_status_event', 'event_type': 'snapshot', 'data': status},
        )
    except Exception as e:
        logger.error(f"push_freeswitch_status_update error: {e}")


def _extract_extension(reg_user: str):
    """
    Extract the bare extension number from a FreeSWITCH reg_user string.
    Handles formats: "1001", "1001-tenantcode", "1001@domain.com"
    Returns the numeric prefix if it looks like an extension (2-10 digits), else None.
    """
    if not reg_user:
        return None
    # Strip domain part first
    local = reg_user.split('@')[0]
    # Take the part before the first dash (tenant code separator)
    part = local.split('-')[0]
    if part.isdigit() and 2 <= len(part) <= 10:
        return part
    return None


def _looks_like_extension(value: str) -> bool:
    """Return True if value looks like an internal extension number (2-7 digits)."""
    return bool(value and value.isdigit() and 2 <= len(value) <= 7)


_STATUS_PRIORITY = {'ringing': 3, 'in_use': 2, 'online': 1}


def _set_status(status_map: dict, ext: str, new_status: str):
    """Apply new_status only if it has higher priority than the current one."""
    if not ext:
        return
    current = status_map.get(ext)
    if current is None or _STATUS_PRIORITY.get(new_status, 0) > _STATUS_PRIORITY.get(current, 0):
        status_map[ext] = new_status


def _build_extension_status_map() -> dict:
    """
    Build a {extension_number: status} map by combining:
      - show registrations as json  → online
      - show channels as json       → ringing / in_use

    Status priority: ringing > in_use > online
    Extensions absent from all data sources are simply not included in the map;
    the frontend treats missing keys as "Active" for enabled or "Disabled" for disabled.
    """
    from .client import get_esl_client
    from .views import _normalize_json_rows

    esl = get_esl_client()
    status_map: dict = {}

    # ── Registrations → online ──────────────────────────────────────────────
    try:
        raw_regs = esl.show_registrations()
        for row in _normalize_json_rows(raw_regs):
            ext = _extract_extension(row.get('reg_user', ''))
            _set_status(status_map, ext, 'online')
    except Exception as e:
        logger.warning(f"_build_extension_status_map: registrations fetch failed: {e}")

    # ── Channels → ringing / in_use ─────────────────────────────────────────
    try:
        raw_channels = esl.show_channels()
        for row in _normalize_json_rows(raw_channels):
            callstate = (row.get('callstate') or row.get('state') or '').upper()
            dest   = row.get('dest', '')
            cid    = row.get('cid_num', '')

            # Use _extract_extension to handle "1001-TENANT" and plain "1001" formats.
            # _looks_like_extension fails for tenant-suffixed destinations like "1001-IHS".
            dest_ext = _extract_extension(dest) if dest else None
            cid_ext  = _extract_extension(cid)  if cid  else None

            if 'RING' in callstate:
                # The destination extension is ringing
                if dest_ext:
                    _set_status(status_map, dest_ext, 'ringing')
            elif 'ACTIVE' in callstate or 'EXECUTE' in callstate:
                # Both legs are in use
                if dest_ext:
                    _set_status(status_map, dest_ext, 'in_use')
                if cid_ext:
                    _set_status(status_map, cid_ext, 'in_use')
    except Exception as e:
        logger.warning(f"_build_extension_status_map: channels fetch failed: {e}")

    return status_map


@shared_task
def push_extension_status_update():
    """
    Build the extension status map (registrations + active channels) and broadcast
    a full snapshot to all connected ExtensionStatusConsumer WebSocket clients.

    Scheduled via Celery Beat every 5 seconds.
    """
    try:
        status_map = _build_extension_status_map()
        async_to_sync(channel_layer.group_send)(
            'extension_status',
            {
                'type': 'extension_status_event',
                'payload': {
                    'type': 'extension_status_snapshot',
                    'extensions': status_map,
                },
            },
        )
        logger.debug(f"push_extension_status_update: broadcast {len(status_map)} extensions")
    except Exception as e:
        logger.error(f"push_extension_status_update error: {e}")


@shared_task
def push_db_status_update():
    """Quick DB health check (SELECT 1) and broadcast latency."""
    try:
        start = time.time()
        with connections['default'].cursor() as cur:
            cur.execute('SELECT 1')
            cur.fetchone()
        latency = time.time() - start
        payload = {'ok': True, 'latency': latency, 'timestamp': int(time.time())}
    except Exception as e:
        payload = {'ok': False, 'error': str(e), 'timestamp': int(time.time())}
    try:
        async_to_sync(channel_layer.group_send)(
            'db_status',
            {'type': 'db_status_event', 'event_type': 'snapshot', 'data': payload},
        )
    except Exception as e:
        logger.error(f"push_db_status_update error: {e}")
