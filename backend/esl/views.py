"""
DRF views for FreeSWITCH API access via the ESL client.
"""
import json
import re
import time
import logging
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework import status

from .client import get_esl_client

logger = logging.getLogger('esl')


# ── Helpers ──────────────────────────────────────────────────────────────────

def _parse_fs_status(raw_status: str, raw_version: str) -> dict:
    """Parse raw FreeSWITCH 'status' + 'version' text into a structured dict."""
    raw_status = raw_status or ''
    raw_version = raw_version or ''
    result = {
        'running': 'is ready' in raw_status,
        'version': None,
        'sessions_active': 0,
        'sessions_since_startup': 0,
        'sessions_peak': 0,
        'sessions_peak_5min': 0,
        'sessions_per_sec': 0,
        'sessions_per_sec_peak': 0,
        'sessions_per_sec_max': 0,
        'max_sessions': 0,
        'uptime': 0,
        'cpu_idle': None,
        'cpu_idle_min': None,
        # legacy key kept for backward compat
        'calls': 0,
    }

    # Version: "FreeSWITCH Version 1.10.7  (git ...)"
    m = re.search(r'FreeSWITCH Version ([\d.]+)', raw_version)
    if m:
        result['version'] = m.group(1)

    # Uptime: "UP 0 years, 1 days, 12 hours, 30 minutes, 45 seconds"
    m = re.search(r'UP\s+(.*?)(?:\n|$)', raw_status)
    if m:
        uptime_str = m.group(1)
        secs = 0
        for unit, mult in [('year', 365*24*3600), ('day', 24*3600),
                            ('hour', 3600), ('minute', 60), ('second', 1)]:
            um = re.search(r'(\d+)\s+' + unit, uptime_str)
            if um:
                secs += int(um.group(1)) * mult
        result['uptime'] = secs

    # Sessions since startup: "10 session(s) since startup"
    m = re.search(r'(\d+)\s+session\(s\)\s+since startup', raw_status)
    if m:
        result['sessions_since_startup'] = int(m.group(1))

    # Active sessions + peak: "2 session(s) - peak 5, last 5min 2"
    m = re.search(r'(\d+)\s+session\(s\)\s+-\s+peak\s+(\d+),\s+last 5min\s+(\d+)', raw_status)
    if m:
        result['sessions_active'] = int(m.group(1))
        result['sessions_peak'] = int(m.group(2))
        result['sessions_peak_5min'] = int(m.group(3))
        result['calls'] = int(m.group(1))

    # Sessions/sec: "0 session(s) per Sec out of max 30, peak 2, last 5min 0"
    m = re.search(r'(\d+)\s+session\(s\)\s+per Sec out of max\s+(\d+),\s+peak\s+(\d+),\s+last 5min\s+(\d+)', raw_status)
    if m:
        result['sessions_per_sec'] = int(m.group(1))
        result['sessions_per_sec_max'] = int(m.group(2))
        result['sessions_per_sec_peak'] = int(m.group(3))

    # Max sessions: "1000 session(s) max"
    m = re.search(r'(\d+)\s+session\(s\)\s+max', raw_status)
    if m:
        result['max_sessions'] = int(m.group(1))

    # CPU idle: "min idle cpu 0.00/79.78" → min_idle/current_idle
    m = re.search(r'min idle cpu\s+([\d.]+)/([\d.]+)', raw_status)
    if m:
        result['cpu_idle_min'] = float(m.group(1))
        result['cpu_idle'] = float(m.group(2))

    return result


def _parse_sofia_status(raw: str) -> list:
    """Parse 'sofia status' text output into a list of profile dicts."""
    profiles = []
    for line in (raw or '').split('\n'):
        line = line.strip()
        parts = line.split()
        if len(parts) >= 3 and parts[1] == 'profile':
            state_m = re.search(r'(RUNNING|STOPPED|RESTARTING)(?:\s*\(\d+\))?', line)
            state = state_m.group(0) if state_m else 'UNKNOWN'
            sip_uri = next((p for p in parts if p.startswith('sip:')), '')
            profiles.append({
                'name': parts[0],
                'type': parts[1],
                'data': sip_uri,
                'state': state,
                'running': 'RUNNING' in state,
            })
    return profiles


def _parse_elapsed(val) -> int:
    """Convert FreeSWITCH elapsed_time to integer seconds.
    FreeSWITCH returns either an int or a string like '0:00:05' or '00:05'."""
    if isinstance(val, int):
        return val
    try:
        parts = str(val).split(':')
        parts = [int(p) for p in parts]
        if len(parts) == 3:
            return parts[0] * 3600 + parts[1] * 60 + parts[2]
        if len(parts) == 2:
            return parts[0] * 60 + parts[1]
        return int(parts[0])
    except (ValueError, AttributeError):
        return 0


def _normalize_json_rows(raw: str) -> list:
    """Parse FreeSWITCH 'show X as json' output into a plain list."""
    if not raw:
        return []
    try:
        data = json.loads(raw)
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            return data.get('rows') or data.get('result') or []
    except (json.JSONDecodeError, TypeError):
        pass
    return []


# ── Views ─────────────────────────────────────────────────────────────────────

class FSStatusView(APIView):
    """
    GET /api/v1/freeswitch/status/
    Returns parsed FreeSWITCH status as structured JSON.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            esl = get_esl_client()
            raw_version = esl.version()
            raw_status = esl.fs_status()
            parsed = _parse_fs_status(raw_status, raw_version)
            parsed['connected'] = True
            return Response(parsed)
        except Exception as e:
            logger.error(f"FSStatusView error: {e}")
            return Response(
                {'error': str(e), 'connected': False, 'running': False},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )


class FSApiView(APIView):
    """
    POST /api/v1/freeswitch/api/
    Execute an arbitrary FreeSWITCH API command. Admin only.
    """
    permission_classes = [IsAdminUser]

    def post(self, request):
        command = request.data.get('command', '').strip()
        if not command:
            return Response(
                {'error': 'command is required'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            esl = get_esl_client()
            result = esl.api(command)
            return Response({'command': command, 'result': result})
        except Exception as e:
            logger.error(f"FSApiView error ({command}): {e}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )


def _tenant_code_for_request(request):
    """Return the tenant_code for the current request.
    For superusers, resolves from the ?tenant=<uuid> query param sent by the frontend.
    Returns None only if no tenant can be determined (should not happen in normal use).
    """
    # Superuser/staff: ?tenant= param takes priority over the user's own tenant binding
    if request.user.is_authenticated and (request.user.is_superuser or request.user.is_staff):
        tenant_uuid = request.query_params.get('tenant') or request.GET.get('tenant')
        if tenant_uuid:
            from core.models import Tenant
            t = Tenant.objects.filter(tenant_uuid=tenant_uuid).first()
            return t.tenant_code if t else None
    tenant = getattr(request, 'tenant', None)
    if tenant:
        return tenant.tenant_code
    return None


def _call_belongs_to_tenant(row: dict, tenant_code: str) -> bool:
    """Return True if this call row belongs to the given tenant.
    Matches on cid_num or dest containing '-{tenant_code}' (SIP username format)."""
    suffix = f'-{tenant_code}'
    return (
        str(row.get('cid_num', '')).endswith(suffix) or
        str(row.get('dest', '')).endswith(suffix) or
        str(row.get('username', '')).endswith(suffix)
    )


def _reg_belongs_to_tenant(row: dict, tenant_code: str) -> bool:
    """Return True if this registration row belongs to the given tenant."""
    suffix = f'-{tenant_code}'
    return str(row.get('reg_user', '') or row.get('user', '')).endswith(suffix)


class FSCallsView(APIView):
    """
    GET /api/v1/freeswitch/calls/
    Returns active calls as a normalized list, filtered to the current tenant.
    Superusers/staff see all calls.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            esl = get_esl_client()
            raw = esl.show_calls()
            rows = _normalize_json_rows(raw)
            tenant_code = _tenant_code_for_request(request)
            if tenant_code:
                rows = [r for r in rows if _call_belongs_to_tenant(r, tenant_code)]
            calls = [
                {
                    'uuid':     row.get('uuid', ''),
                    'cid_name': row.get('cid_name', ''),
                    'cid_num':  row.get('cid_num', ''),
                    'dest':     row.get('dest', ''),
                    'state':    row.get('callstate') or row.get('state', ''),
                    'answered': row.get('callstate') == 'ACTIVE',
                    'duration': _parse_elapsed(row.get('elapsed_time', 0)),
                }
                for row in rows
            ]
            return Response({'calls': calls})
        except Exception as e:
            logger.error(f"FSCallsView error: {e}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )


class FSChannelsView(APIView):
    """
    GET /api/v1/freeswitch/channels/
    Returns active channels as a normalized list.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            esl = get_esl_client()
            raw = esl.show_channels()
            rows = _normalize_json_rows(raw)
            return Response({'channels': rows})
        except Exception as e:
            logger.error(f"FSChannelsView error: {e}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )


class FSRegistrationsView(APIView):
    """
    GET /api/v1/freeswitch/registrations/
    Returns SIP registrations as a normalized list, filtered to the current tenant.
    Superusers/staff see all registrations.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            esl = get_esl_client()
            raw = esl.show_registrations()
            rows = _normalize_json_rows(raw)
            tenant_code = _tenant_code_for_request(request)
            if tenant_code:
                rows = [r for r in rows if _reg_belongs_to_tenant(r, tenant_code)]
            now = int(time.time())
            registrations = []
            for row in rows:
                # Convert absolute epoch expiry to remaining seconds
                exp_raw = row.get('expires', '')
                try:
                    remaining = int(exp_raw) - now
                    expires = str(max(0, remaining))
                except (ValueError, TypeError):
                    expires = exp_raw
                registrations.append({
                    'user':         row.get('reg_user') or row.get('user', ''),
                    'realm':        row.get('realm', ''),
                    'network_ip':   row.get('network_ip', ''),
                    'network_port': row.get('network_port', ''),
                    'user_agent':   row.get('user_agent', ''),
                    'url':          row.get('url', ''),
                    'call_id':      row.get('call_id', ''),
                    'profile':      row.get('profile', 'internal'),
                    'expires':      expires,
                })
            return Response({'registrations': registrations})
        except Exception as e:
            logger.error(f"FSRegistrationsView error: {e}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )


class FSDeregisterView(APIView):
    """
    POST /api/v1/freeswitch/deregister/
    De-register a SIP device by Call-ID.
    Body: { "call_id": "...", "profile": "internal" }
    Non-superusers can only deregister devices belonging to their own tenant.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        call_id = request.data.get('call_id', '').strip()
        profile = request.data.get('profile', 'internal').strip()
        if not call_id:
            return Response({'error': 'call_id is required'}, status=status.HTTP_400_BAD_REQUEST)
        # Resolve tenant_code — required for everyone including superusers
        tenant_code = _tenant_code_for_request(request)
        if not tenant_code:
            # Superuser must supply tenant_code in the request body
            tenant_code = request.data.get('tenant_code', '').strip()
        if not tenant_code:
            return Response({'error': 'tenant_code is required.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            esl = get_esl_client()
            raw = esl.show_registrations()
            rows = _normalize_json_rows(raw)
            rows = [r for r in rows if _reg_belongs_to_tenant(r, tenant_code)]
            match = next((r for r in rows if r.get('call_id') == call_id), None)
            if not match:
                return Response({'error': 'Registration not found.'}, status=status.HTTP_404_NOT_FOUND)
            result = esl.flush_registration(call_id, profile)
            return Response({'result': result})
        except Exception as e:
            logger.error(f"FSDeregisterView error: {e}")
            return Response({'error': str(e)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)


class FSOriginateView(APIView):
    """
    POST /api/v1/freeswitch/originate/
    Originate a call (click-to-call).

    Accepts either:
      { "caller": "1001", "callee": "1002" }   (simple extension numbers)
    or:
      { "src": "user/1001@domain", "dst": "1002" }  (raw ESL format)
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        caller = request.data.get('caller', '').strip()
        callee = request.data.get('callee', '').strip()
        src = request.data.get('src', caller).strip()
        dst = request.data.get('dst', callee).strip()

        if not src or not dst:
            return Response(
                {'error': 'caller/callee (or src/dst) are required'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Normalize to 10-digit NANP format so the dialplan ^(\d{10})$ route matches.
        # Strip leading + (E.164), then strip leading country code 1 from 11-digit numbers.
        if dst.startswith('+'):
            dst = dst[1:]
        if len(dst) == 11 and dst.startswith('1'):
            dst = dst[1:]

        tenant_code = _tenant_code_for_request(request)
        context = f'default-{tenant_code}' if tenant_code else 'default'

        # If src is a plain extension number (no / or @), wrap as user/ endpoint
        # and append the tenant suffix so FreeSWITCH resolves the right directory user
        if '/' not in src and '@' not in src:
            if tenant_code and not src.endswith(f'-{tenant_code}'):
                src = f'user/{src}-{tenant_code}'
            else:
                src = f'user/{src}'

        caller_id_name = request.data.get('caller_id_name', '')
        caller_id_number = request.data.get('caller_id_number', '')

        try:
            esl = get_esl_client()
            result = esl.originate(src, dst,
                                   context=context,
                                   caller_id_name=caller_id_name,
                                   caller_id_number=caller_id_number)
            return Response({'result': result})
        except Exception as e:
            logger.error(f"FSOriginateView error: {e}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )


class FSHangupView(APIView):
    """
    POST /api/v1/freeswitch/hangup/
    Hangup a call by channel UUID.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        uuid = request.data.get('uuid', '').strip()
        if not uuid:
            return Response(
                {'error': 'uuid is required'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        cause = request.data.get('cause', 'NORMAL_CLEARING')
        try:
            esl = get_esl_client()
            result = esl.hangup(uuid, cause)
            return Response({'uuid': uuid, 'result': result})
        except Exception as e:
            logger.error(f"FSHangupView error: {e}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )


class FSTransferView(APIView):
    """
    POST /api/v1/freeswitch/transfer/
    Transfer a call to an extension.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        uuid = request.data.get('uuid', '').strip()
        extension = request.data.get('extension', '').strip()
        if not uuid or not extension:
            return Response(
                {'error': 'uuid and extension are required'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        dialplan = request.data.get('dialplan', 'XML')
        context = request.data.get('context', 'default')
        try:
            esl = get_esl_client()
            result = esl.transfer(uuid, extension, dialplan, context)
            return Response({'uuid': uuid, 'extension': extension, 'result': result})
        except Exception as e:
            logger.error(f"FSTransferView error: {e}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )


class FSEavesdropView(APIView):
    """
    POST /api/v1/freeswitch/eavesdrop/
    Originate a call from a supervisor extension to eavesdrop on an active call.
    FreeSWITCH calls the supervisor's phone; when answered, they hear/speak on the target call.

    Body:
      uuid    — UUID of the call channel to spy on
      spy_ext — extension number of the supervisor (the listener)
      mode    — 'listen' | 'whisper' | 'barge'  (default: listen)
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        uuid = request.data.get('uuid', '').strip()
        spy_ext = request.data.get('spy_ext', '').strip()
        mode = request.data.get('mode', 'listen').strip()

        if not uuid or not spy_ext:
            return Response(
                {'error': 'uuid and spy_ext are required'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Resolve domain + tenant from the current request context
        from core.models import Domain
        tenant = getattr(request, 'tenant', None)
        domain_obj = Domain.objects.filter(
            domain_enabled=True,
            **({'tenant': tenant} if tenant else {})
        ).first()
        domain_name = domain_obj.domain_name if domain_obj else ''
        tenant_code = tenant.tenant_code if tenant else ''

        if not domain_name:
            from django.conf import settings
            domain_name = getattr(settings, 'PBX_DEFAULT_DOMAIN', None)

        context = f'default-{tenant_code}' if tenant_code else 'default'

        # SIP user format: ext-TENANTCODE@domain
        sip_user = f'{spy_ext}-{tenant_code}@{domain_name}' if tenant_code else f'{spy_ext}@{domain_name}'

        # Map mode to eavesdrop dialplan application flags
        mode_flags = {'listen': 'r', 'whisper': 'w', 'barge': 'rw'}.get(mode, 'r')

        try:
            esl = get_esl_client()
            # Originate supervisor's phone and drop into eavesdrop on the target UUID
            cmd = (
                f"originate {{"
                f"origination_caller_id_name='Supervisor',"
                f"origination_caller_id_number='{spy_ext}',"
                f"eavesdrop_uuid='{uuid}',"
                f"eavesdrop_flags='{mode_flags}'"
                f"}}user/{sip_user} "
                f"eavesdrop XML {context}"
            )
            result = esl.api(cmd)
            return Response({'uuid': uuid, 'spy_ext': spy_ext, 'mode': mode, 'result': result})
        except Exception as e:
            logger.error(f"FSEavesdropView error: {e}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )


class FSSofiaView(APIView):
    """
    GET /api/v1/freeswitch/sofia/
    Returns parsed Sofia SIP profile statuses.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            esl = get_esl_client()
            raw = esl.sofia_status()
            profiles = _parse_sofia_status(raw)
            return Response({'profiles': profiles})
        except Exception as e:
            logger.error(f"FSSofiaView error: {e}")
            return Response(
                {'error': str(e), 'profiles': []},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )


class FSLogView(APIView):
    """
    GET /api/v1/freeswitch/log/
    Returns last N lines of the FreeSWITCH log file. Superadmin only.
    Query params: lines (default 200), level (filter by log level), search (substring filter)
    """
    permission_classes = [IsAdminUser]

    LOG_PATH = '/var/log/freeswitch/freeswitch.log'

    def get(self, request):
        if not request.user.is_superuser:
            from rest_framework import status as drf_status
            return Response({'error': 'Superadmin only'}, status=drf_status.HTTP_403_FORBIDDEN)

        try:
            lines = min(int(request.query_params.get('lines', 200)), 2000)
        except (ValueError, TypeError):
            lines = 200

        level_filter = request.query_params.get('level', '').upper()
        search_filter = request.query_params.get('search', '').lower()

        try:
            import subprocess as sp
            result = sp.run(
                ['tail', '-n', str(lines), self.LOG_PATH],
                capture_output=True, text=True, timeout=5
            )
            raw_lines = result.stdout.splitlines()
        except FileNotFoundError:
            return Response({'error': f'Log file not found: {self.LOG_PATH}', 'lines': []})
        except Exception as e:
            return Response({'error': str(e), 'lines': []})

        parsed = []
        for line in raw_lines:
            level = 'INFO'
            if 'WARNING' in line or 'WARN' in line:
                level = 'WARNING'
            elif 'ERR' in line or 'ERROR' in line or 'CRIT' in line:
                level = 'ERROR'
            elif 'DEBUG' in line:
                level = 'DEBUG'
            elif 'NOTICE' in line:
                level = 'NOTICE'

            if level_filter and level != level_filter:
                continue
            if search_filter and search_filter not in line.lower():
                continue

            parsed.append({'level': level, 'text': line})

        return Response({'lines': parsed, 'total': len(parsed), 'log_path': self.LOG_PATH})


class FSServerHealthView(APIView):
    """
    GET /api/v1/freeswitch/server-health/
    Returns OS-level stats, Django, DB, and Celery health.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        import os, shutil, time
        import psutil

        # --- CPU ---
        try:
            load1, load5, load15 = os.getloadavg()
            cpu_count = os.cpu_count() or 1
            cpu_pct = psutil.cpu_percent(interval=0.2)
        except Exception:
            load1 = load5 = load15 = cpu_pct = None
            cpu_count = None

        # --- Memory ---
        try:
            mem = psutil.virtual_memory()
            mem_total_gb  = round(mem.total  / (1024**3), 2)
            mem_used_gb   = round(mem.used   / (1024**3), 2)
            mem_cached_gb = round(getattr(mem, 'cached', 0) / (1024**3), 2)
            mem_pct       = round(mem.percent, 1)
        except Exception:
            mem_total_gb = mem_used_gb = mem_cached_gb = mem_pct = None

        # --- Swap ---
        try:
            swap = psutil.swap_memory()
            swap_used_gb  = round(swap.used  / (1024**3), 2)
            swap_total_gb = round(swap.total / (1024**3), 2)
            swap_pct      = round(swap.percent, 1)
        except Exception:
            swap_used_gb = swap_total_gb = swap_pct = None

        # --- Disks ---
        def disk_info(path):
            try:
                d = shutil.disk_usage(path)
                return {
                    'used_gb':  round(d.used  / (1024**3), 2),
                    'total_gb': round(d.total / (1024**3), 2),
                    'pct':      round(d.used / d.total * 100, 1) if d.total else 0,
                }
            except Exception:
                return None

        # Deduplicate disks by device
        seen_devices = set()
        disks = {}
        for path in ['/', '/boot', '/boot/efi']:
            try:
                dev = os.stat(path).st_dev
                if dev in seen_devices:
                    continue
                seen_devices.add(dev)
                info = disk_info(path)
                if info:
                    disks[path] = info
            except Exception:
                pass

        # --- Network I/O ---
        try:
            net = psutil.net_io_counters()
            net_info = {
                'bytes_sent_gb': round(net.bytes_sent / (1024**3), 2),
                'bytes_recv_gb': round(net.bytes_recv / (1024**3), 2),
            }
        except Exception:
            net_info = None

        # --- Uptime ---
        try:
            uptime_sec = int(time.time() - psutil.boot_time())
        except Exception:
            uptime_sec = None

        # --- Process count ---
        try:
            process_count = len(psutil.pids())
        except Exception:
            process_count = None

        # --- Django health ---
        django_ok = True

        # --- DB health ---
        try:
            from django.db import connection
            connection.ensure_connection()
            db_ok = True
            db_error = None
        except Exception as e:
            db_ok = False
            db_error = str(e)

        # --- Celery health ---
        try:
            from config.celery import app as celery_app
            insp = celery_app.control.inspect(timeout=2)
            ping = insp.ping()
            celery_ok = bool(ping)
            celery_workers = list(ping.keys()) if ping else []
        except Exception:
            celery_ok = False
            celery_workers = []

        return Response({
            'system': {
                'uptime_sec': uptime_sec,
                'process_count': process_count,
                'load_avg': {
                    '1min':  round(load1, 2)  if load1  is not None else None,
                    '5min':  round(load5, 2)  if load5  is not None else None,
                    '15min': round(load15, 2) if load15 is not None else None,
                },
                'cpu': {
                    'cores': cpu_count,
                    'pct':   round(cpu_pct, 1) if cpu_pct is not None else None,
                },
                'memory': {
                    'used_gb':   mem_used_gb,
                    'total_gb':  mem_total_gb,
                    'cached_gb': mem_cached_gb,
                    'pct':       mem_pct,
                },
                'swap': {
                    'used_gb':  swap_used_gb,
                    'total_gb': swap_total_gb,
                    'pct':      swap_pct,
                },
                'disks': disks,
                'network': net_info,
            },
            'health': {
                'django':   {'ok': django_ok},
                'database': {'ok': db_ok, 'error': db_error},
                'celery':   {'ok': celery_ok, 'workers': celery_workers},
            },
        })


class FSDbStatsView(APIView):
    """
    GET /api/v1/freeswitch/db-stats/
    Returns counts of PBX resources in the database.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from apps.extensions.models import Extension
        from apps.voicemails.models import Voicemail
        from apps.gateways.models import Gateway
        from apps.ring_groups.models import RingGroup
        from apps.ivr_menus.models import IvrMenu
        from apps.destinations.models import Destination
        from apps.devices.models import Device
        from apps.conferences.models import Conference
        from apps.call_centers.models import CallCenter
        from apps.dialplans.models import Dialplan
        from core.models import Tenant, Domain

        def safe_count(model):
            try:
                return model.objects.count()
            except Exception:
                return None

        return Response({
            'extensions':   safe_count(Extension),
            'voicemails':   safe_count(Voicemail),
            'gateways':     safe_count(Gateway),
            'ring_groups':  safe_count(RingGroup),
            'ivr_menus':    safe_count(IvrMenu),
            'destinations': safe_count(Destination),
            'devices':      safe_count(Device),
            'conferences':  safe_count(Conference),
            'call_centers': safe_count(CallCenter),
            'dialplans':    safe_count(Dialplan),
            'tenants':      safe_count(Tenant),
            'domains':      safe_count(Domain),
        })
