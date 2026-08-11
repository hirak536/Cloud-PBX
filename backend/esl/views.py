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


# Sentinel returned when a non-superuser cannot be resolved to a tenant they are
# authorized for. Callers MUST treat this as "return nothing" — never as "no
# filter", which would leak every tenant's data.
_TENANT_DENY = object()


def _tenant_code_for_request(request):
    """Resolve the tenant_code a request is scoped to.

    Rules (fail-closed for non-superusers):
      * Superuser: ?tenant=<uuid> selects any tenant; None (no param) = all tenants.
      * Everyone else: ?tenant=<uuid> is honored ONLY if the user is bound to that
        tenant (via user.tenant) or administers it (admin_tenants M2M). Otherwise,
        fall back to the user's own tenant. If neither yields an authorized tenant,
        return _TENANT_DENY so the caller returns an empty result rather than
        exposing other tenants' data.

    Returns: a tenant_code str, None (superuser = unscoped), or _TENANT_DENY.
    """
    from core.models import Tenant

    user = request.user
    if not user.is_authenticated:
        return _TENANT_DENY

    requested_uuid = request.query_params.get('tenant') or request.GET.get('tenant')

    # Superuser: full cross-tenant visibility, optionally narrowed by ?tenant=.
    if user.is_superuser:
        if requested_uuid:
            t = Tenant.objects.filter(tenant_uuid=requested_uuid).first()
            return t.tenant_code if t else _TENANT_DENY
        return None  # unscoped — sees all

    # Non-superuser: build the set of tenants this user may view.
    own_tenant = getattr(user, 'tenant', None)
    allowed = {}
    if own_tenant:
        allowed[str(own_tenant.tenant_uuid)] = own_tenant.tenant_code
    # Tenant admins (own tenant FK is typically null) manage tenants via M2M.
    for t in user.admin_tenants.all():
        allowed[str(t.tenant_uuid)] = t.tenant_code

    if not allowed:
        return _TENANT_DENY

    if requested_uuid:
        # Honor the selection only if the user is authorized for it.
        code = allowed.get(str(requested_uuid))
        return code if code is not None else _TENANT_DENY

    # No explicit selection: if the user administers exactly one tenant, use it.
    if len(allowed) == 1:
        return next(iter(allowed.values()))
    # Ambiguous (multi-tenant admin, no selection) — deny rather than leak.
    return _TENANT_DENY


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


# Matches the user part of a FreeSWITCH channel name, e.g.
# "sofia/internal/101-DUA@23.189.208.80" or "sofia/webrtc/1000-IHDT@fs1.ihs.host".
_CHAN_USER_RE = re.compile(r'^[^/]+/[^/]+/([^@/]+)')

# WebRTC (SIP.js/JsSIP) clients register from a random per-session instance
# domain ending in ".invalid", with an equally random user part.
_WEBRTC_HOST_RE = re.compile(r'@[^@/;]*\.invalid\b', re.IGNORECASE)


def _is_webrtc_token(value) -> bool:
    """True if this identity is an opaque WebRTC instance token, not an extension."""
    return bool(_WEBRTC_HOST_RE.search(str(value or '')))


def _dedupe_call_legs(rows) -> list:
    """Collapse a bridged call's two legs into a single row.

    'show calls' reports one row per channel, so a bridged call appears twice —
    once for the A-leg (dest = what the caller dialed, e.g. "1001") and once for
    the B-leg (dest = the answering endpoint, e.g. "1000-IHDT"). Both describe
    the same conversation, so the UI must show one row.

    Legs are paired via b_uuid: one row's `uuid` is its partner's `b_uuid`. Note
    the pairing is usually mutual (each row names the other), so "is some row's
    b_uuid" alone cannot pick a winner — that would discard both. Instead each
    pair is claimed once, preferring the leg that looks like the caller side so
    cid_num stays the external caller; _connected_extension() then derives the
    answering extension from that row's own B-leg fields.
    """
    rows = list(rows or [])
    by_uuid = {}
    for r in rows:
        u = str(r.get('uuid') or '').strip()
        if u:
            by_uuid.setdefault(u, r)

    def _is_caller_leg(row):
        """Prefer the leg whose destination is what was dialed, not an identity.

        The callee-side row's `dest` is the answering endpoint itself, which
        equals its own channel identity; the caller-side row's `dest` is the
        dialed number. Inbound direction is the tiebreaker.
        """
        dest = str(row.get('dest') or '').strip()
        name_user = ''
        m = _CHAN_USER_RE.match(str(row.get('name') or ''))
        if m:
            name_user = m.group(1).split('@')[0]
        if dest and name_user and dest == name_user:
            return False
        return str(row.get('direction') or '') == 'inbound'

    deduped, claimed = [], set()
    for r in rows:
        u = str(r.get('uuid') or '').strip()
        b = str(r.get('b_uuid') or '').strip()

        if u and u in claimed:
            continue

        partner = by_uuid.get(b) if b else None
        if partner is not None and str(partner.get('uuid') or '') != u:
            # A bridged pair: emit exactly one row for it.
            keep = r if _is_caller_leg(r) else (
                partner if _is_caller_leg(partner) else r)
            keep_uuid = str(keep.get('uuid') or '').strip()
            if keep_uuid in claimed:
                continue
            claimed.update({x for x in (u, b) if x})
            deduped.append(keep)
            continue

        if u:
            claimed.add(u)
        deduped.append(r)
    return deduped


def _webrtc_token_map_for(esl, rows) -> dict:
    """Build the WebRTC token map only if some call actually has a WebRTC leg.

    Avoids an extra ESL round-trip (show registrations) on the common case where
    every leg is a plain SIP endpoint.
    """
    if not any(_is_webrtc_token(r.get('b_name')) or _is_webrtc_token(r.get('name'))
               for r in rows):
        return {}
    try:
        return _webrtc_token_map(_normalize_json_rows(esl.show_registrations()))
    except Exception:
        logger.exception('WebRTC token map build failed')
        return {}


def _webrtc_token_map(reg_rows) -> dict:
    """Map WebRTC instance tokens -> registered extension, from registration rows.

    WebRTC legs identify themselves as "<token>@<random>.invalid" on the channel,
    so the only way back to the SIP username is the registration whose contact
    carries that token.
    """
    mapping = {}
    for row in reg_rows or []:
        user = str(row.get('reg_user') or row.get('user') or '').split('@')[0].strip()
        contact = str(row.get('full_contact') or row.get('contact') or row.get('url') or '')
        if not user or not contact:
            continue
        m = re.search(r'sip:([^@;>]+)@[^@/;>]*\.invalid', contact, re.IGNORECASE)
        if m:
            mapping[m.group(1)] = user
    return mapping


def _connected_extension(row: dict, webrtc_map: dict = None) -> str:
    """Return the extension the call is actually connected to.

    `dest` is what the caller originally dialed — a DID, an IVR entry, a ring
    group number — so it does not say who ultimately answered. Once the call is
    bridged, FreeSWITCH exposes the answering party on the B-leg, so prefer that
    and fall back to `dest` while the call is still ringing (no B-leg yet).

    Preference order:
      1. b_presence_id / presence_id user part — the directory identity of the
         answering endpoint ("101-DUA"), set for registered extensions.
      2. B-leg channel name user part — same identity for internal legs.
      3. callee_num / b_dest — covers external transfer targets.
      4. dest — original dialed number (call not yet bridged).

    WebRTC endpoints register under an opaque per-session instance token
    ("8cau5n53@ji6jb5vt147c.invalid") instead of their SIP username, so the
    B-leg identity is meaningless on its own. `webrtc_map` (built by
    _webrtc_token_map()) translates such a token back to its real extension;
    without it, a WebRTC leg falls through to the dialed number rather than
    displaying a token.
    """
    def _user_part(value):
        value = str(value or '').strip()
        if not value:
            return ''
        # presence_id is "user@domain"; channel names are "sofia/profile/user@domain".
        if '/' in value:
            m = _CHAN_USER_RE.match(value)
            value = m.group(1) if m else value.rsplit('/', 1)[-1]
        return value.split('@')[0].strip()

    webrtc_map = webrtc_map or {}
    # Bare identity fields (b_dest, callee_num) carry the token without the
    # ".invalid" host, so detect a WebRTC answering leg from the channel name
    # and treat this row's identities as tokens throughout.
    b_is_webrtc = _is_webrtc_token(row.get('b_name')) or _is_webrtc_token(row.get('name'))

    def _resolve(value):
        """Map an opaque WebRTC instance token back to its real extension."""
        user = _user_part(value)
        if not user:
            return ''
        if user in webrtc_map:
            return webrtc_map[user]
        # An unresolvable token must not be shown as if it were an extension.
        if b_is_webrtc or _is_webrtc_token(value):
            return ''
        return user

    for key in ('b_presence_id', 'b_name'):
        user = _resolve(row.get(key))
        if user:
            return user

    # A bridged single-leg view (show channels) reports the far end here.
    for key in ('callee_num', 'b_dest', 'sent_callee_num'):
        if str(row.get(key) or '').strip():
            user = _resolve(row.get(key))
            if user:
                return user

    return str(row.get('dest', '') or '')


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
            rows = _dedupe_call_legs(_normalize_json_rows(raw))
            tenant_code = _tenant_code_for_request(request)
            if tenant_code is _TENANT_DENY:
                return Response({'calls': []})
            if tenant_code:
                rows = [r for r in rows if _call_belongs_to_tenant(r, tenant_code)]
            webrtc_map = _webrtc_token_map_for(esl, rows)
            calls = [
                {
                    'uuid':     row.get('uuid', ''),
                    'cid_name': row.get('cid_name', ''),
                    'cid_num':  row.get('cid_num', ''),
                    # Final connected party, not the originally dialed
                    # DID/IVR/ring-group number. See _connected_extension().
                    'dest':     _connected_extension(row, webrtc_map),
                    'dialed':   row.get('dest', ''),
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


def _tenant_code_from_call(row: dict) -> str:
    """Extract the tenant_code embedded in a live call row.

    SIP usernames are formatted `ext-TENANTCODE`, so the tenant code is the
    suffix after the last dash on cid_num / dest / username. Returns '' when no
    tenant marker is present (e.g. raw external legs)."""
    for key in ('cid_num', 'dest', 'username'):
        val = str(row.get(key, '') or '')
        # strip any @domain part first
        val = val.split('@', 1)[0]
        if '-' in val:
            code = val.rsplit('-', 1)[-1]
            if code:
                return code
    return ''


class FSCallsByTenantView(APIView):
    """
    GET /api/v1/freeswitch/calls-by-tenant/
    Superuser/staff only. Returns, per tenant:
      - active:  count of live FreeSWITCH channels attributed to the tenant
      - today:   count of CDR records with start_stamp today (tenant-local)
    plus grand totals. Tenants with no activity today and no active calls are
    omitted.
    """
    permission_classes = [IsAdminUser]

    def get(self, request):
        from django.utils import timezone
        from django.db.models import Count
        from core.models import Tenant
        from apps.xml_cdr.models import XmlCdr

        # ── Live active calls grouped by tenant_code ──────────────────────────
        active_by_code = {}
        total_active = 0
        try:
            esl = get_esl_client()
            rows = _normalize_json_rows(esl.show_calls())
            for row in rows:
                code = _tenant_code_from_call(row)
                active_by_code[code] = active_by_code.get(code, 0) + 1
                total_active += 1
        except Exception as e:
            logger.error(f"FSCallsByTenantView (calls) error: {e}")

        # ── Today's CDR counts grouped by tenant_code ─────────────────────────
        today = timezone.localdate()
        today_by_code = {}
        try:
            cdr_rows = (
                XmlCdr.objects
                .filter(start_stamp__date=today)
                .values('tenant_code')
                .annotate(n=Count('xml_cdr_uuid'))
            )
            today_by_code = {r['tenant_code']: r['n'] for r in cdr_rows}
        except Exception as e:
            logger.error(f"FSCallsByTenantView (cdr) error: {e}")

        # ── Resolve names & merge ─────────────────────────────────────────────
        codes = {c for c in (set(active_by_code) | set(today_by_code)) if c}
        name_by_code = {
            t.tenant_code: t.tenant_name
            for t in Tenant.objects.filter(tenant_code__in=codes)
        }

        tenants = []
        for code in codes:
            tenants.append({
                'tenant_code': code,
                'tenant_name': name_by_code.get(code, code or 'Unknown'),
                'active': active_by_code.get(code, 0),
                'today': today_by_code.get(code, 0),
            })
        # Unattributed live legs (no tenant marker), if any
        unknown_active = active_by_code.get('', 0)
        if unknown_active:
            tenants.append({
                'tenant_code': '',
                'tenant_name': 'Unattributed',
                'active': unknown_active,
                'today': today_by_code.get('', 0),
            })

        tenants.sort(key=lambda t: (-t['active'], -t['today'], t['tenant_name'].lower()))

        return Response({
            'tenants': tenants,
            'total_active': total_active,
            'total_today': sum(today_by_code.values()),
        })


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
    Returns one row per Extension in the tenant — registered or not — joined
    with live data from sofia (IP, port, contact, user-agent, ping, registered
    since) and the current state from PeerStateHistory.
    Superusers/staff see all extensions in the selected tenant.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from apps.extensions.models import Extension
        from .models import PeerStateHistory
        try:
            esl = get_esl_client()
            raw = esl.show_registrations()
            rows = _normalize_json_rows(raw)
            tenant_code = _tenant_code_for_request(request)
            if tenant_code is _TENANT_DENY:
                return Response({'registrations': []})
            if tenant_code:
                rows = [r for r in rows if _reg_belongs_to_tenant(r, tenant_code)]

            reg_by_user = {}
            for row in rows:
                user = row.get('reg_user') or row.get('user', '')
                if user and user not in reg_by_user:
                    reg_by_user[user] = row

            ext_qs = Extension.objects.filter(enabled=True).select_related('tenant')
            if tenant_code:
                ext_qs = ext_qs.filter(tenant__tenant_code=tenant_code)
            extensions = list(ext_qs)

            sip_usernames = [e.sip_username for e in extensions if e.sip_username]
            current_state = {
                row.extension: row.state
                for row in PeerStateHistory.objects.filter(
                    extension__in=sip_usernames, ended_at__isnull=True
                )
            }

            now = int(time.time())
            registrations = []
            for ext in extensions:
                row = reg_by_user.get(ext.sip_username, {})
                exp_raw = row.get('expires', '')
                try:
                    expires = str(max(0, int(exp_raw) - now))
                except (ValueError, TypeError):
                    expires = exp_raw
                registrations.append({
                    'user':             ext.sip_username,
                    'extension':        ext.extension,
                    'extension_name':   ext.directory_full_name or ext.effective_caller_id_name or '',
                    'realm':            row.get('realm', ''),
                    'network_ip':       row.get('network_ip', ''),
                    'network_port':     row.get('network_port', ''),
                    'user_agent':       row.get('user_agent', ''),
                    'url':              row.get('url', ''),
                    'full_contact':     row.get('full_contact', ''),
                    'call_id':          row.get('call_id', ''),
                    'profile':          row.get('profile', 'internal'),
                    'expires':          expires,
                    'ping_ms':          row.get('ping_ms'),
                    'registered_since': row.get('registered_since'),
                    'state':            current_state.get(
                        ext.sip_username,
                        'available' if row else 'offline',
                    ),
                })
            return Response({'registrations': registrations})
        except Exception as e:
            logger.error(f"FSRegistrationsView error: {e}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )


class FSExtensionStatusView(APIView):
    """
    GET /api/v1/freeswitch/extension-status/
    Returns the current extension status map keyed by sip_username
    ("1001-IHS" → "online" | "ringing" | "in_use"). Extensions absent from the
    map are idle/offline. Fetched on demand by the Extensions page on load —
    there is no live push for this list.
    Superusers/staff are scoped via the ?tenant=<uuid> query param.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from .tasks import _build_extension_status_map
        from apps.extensions.models import Extension
        try:
            status_map = _build_extension_status_map()
        except Exception as e:
            logger.error(f"FSExtensionStatusView error: {e}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        tenant_code = _tenant_code_for_request(request)
        if tenant_code is _TENANT_DENY:
            return Response({'extensions': {}})
        if tenant_code:
            tenant_exts = set(
                Extension.objects.filter(
                    tenant__tenant_code=tenant_code, enabled=True
                ).values_list('sip_username', flat=True)
            )
            status_map = {k: v for k, v in status_map.items() if k in tenant_exts}

        return Response({'extensions': status_map})


class FSPeerHistoryView(APIView):
    """
    GET /api/v1/freeswitch/peer-history/?user=<sip_username>&days=5
    Returns the state-transition history for one peer over the last N days.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from datetime import timedelta
        from django.utils import timezone
        from .models import PeerStateHistory

        sip_username = (request.query_params.get('user') or '').strip()
        if not sip_username:
            return Response({'error': 'user is required'}, status=status.HTTP_400_BAD_REQUEST)

        # Tenant-scope check for non-superusers
        tenant_code = _tenant_code_for_request(request)
        if tenant_code is _TENANT_DENY:
            return Response({'error': 'forbidden'}, status=status.HTTP_403_FORBIDDEN)
        if tenant_code and not sip_username.endswith(f'-{tenant_code}'):
            return Response({'error': 'forbidden'}, status=status.HTTP_403_FORBIDDEN)

        try:
            days = int(request.query_params.get('days', '5'))
        except ValueError:
            days = 5
        days = max(1, min(days, 30))

        since = timezone.now() - timedelta(days=days)
        rows = PeerStateHistory.objects.filter(
            extension=sip_username,
            started_at__gte=since,
        ).order_by('started_at')

        history = [
            {
                'state':      row.state,
                'started_at': row.started_at.isoformat(),
                'ended_at':   row.ended_at.isoformat() if row.ended_at else None,
            }
            for row in rows
        ]
        return Response({'user': sip_username, 'days': days, 'history': history})


class FSRebootView(APIView):
    """
    POST /api/v1/freeswitch/reboot/
    Send SIP NOTIFY check-sync to reboot a desk phone.
    Body: { "call_id": "...", "profile": "internal", "tenant_code": "..." (superuser only) }
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        call_id = request.data.get('call_id', '').strip()
        profile = request.data.get('profile', 'internal').strip() or 'internal'
        if not call_id:
            return Response({'error': 'call_id is required'}, status=status.HTTP_400_BAD_REQUEST)
        tenant_code = _tenant_code_for_request(request)
        if tenant_code is _TENANT_DENY:
            return Response({'error': 'forbidden'}, status=status.HTTP_403_FORBIDDEN)
        if not tenant_code:
            # Only superusers may target a tenant via the request body.
            if not request.user.is_superuser:
                return Response({'error': 'forbidden'}, status=status.HTTP_403_FORBIDDEN)
            tenant_code = request.data.get('tenant_code', '').strip()
        if not tenant_code:
            return Response({'error': 'tenant_code is required.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            esl = get_esl_client()
            raw = esl.show_registrations()
            rows = [r for r in _normalize_json_rows(raw) if _reg_belongs_to_tenant(r, tenant_code)]
            if not any(r.get('call_id') == call_id for r in rows):
                return Response({'error': 'Registration not found.'}, status=status.HTTP_404_NOT_FOUND)
            result = esl.reboot_peer(call_id, profile)
            return Response({'result': result})
        except Exception as e:
            logger.error(f"FSRebootView error: {e}")
            return Response({'error': str(e)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)


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
        if tenant_code is _TENANT_DENY:
            return Response({'error': 'forbidden'}, status=status.HTTP_403_FORBIDDEN)
        if not tenant_code:
            # Only superusers may supply tenant_code in the request body.
            if not request.user.is_superuser:
                return Response({'error': 'forbidden'}, status=status.HTTP_403_FORBIDDEN)
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
        if tenant_code is _TENANT_DENY:
            return Response({'error': 'forbidden'}, status=status.HTTP_403_FORBIDDEN)
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
