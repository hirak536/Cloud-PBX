import os
import logging
from pathlib import Path
from lxml import etree

from rest_framework import viewsets, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter
from django.conf import settings

from core.permissions import IsSuperAdmin
from .models import Gateway
from .serializers import GatewaySerializer

logger = logging.getLogger(__name__)


class GatewayViewSet(viewsets.ModelViewSet):
    """Global gateways — readable by all authenticated users, editable by superadmins only."""
    queryset = Gateway.objects.all()
    serializer_class = GatewaySerializer
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ['gateway_enabled', 'register', 'profile']
    search_fields = ['gateway', 'proxy', 'realm', 'gateway_description']

    def get_permissions(self):
        if self.action in ('list', 'retrieve', 'statuses', 'status'):
            return [permissions.IsAuthenticated()]
        return [permissions.IsAuthenticated(), IsSuperAdmin()]

    @action(detail=False, methods=['get'])
    def statuses(self, request):
        """Return {gateway_name: state} for all gateways by parsing `sofia status` once."""
        try:
            from esl.client import get_esl_client
            esl = get_esl_client()
            raw = esl.sofia_status()
            states = _parse_gateway_states(raw)
            return Response(states)
        except Exception as e:
            return Response({'error': str(e)}, status=503)

    @action(detail=True, methods=['get'])
    def status(self, request, pk=None):
        gw = self.get_object()
        try:
            from esl.client import get_esl_client
            esl = get_esl_client()
            result = esl.gateway_status(gw.gateway)
            return Response({'gateway': gw.gateway, 'status': result})
        except Exception as e:
            return Response({'error': str(e)}, status=503)

    def perform_create(self, serializer):
        super().perform_create(serializer)
        _write_gateway_file(serializer.instance)
        self._trigger_rescan(serializer.instance.profile)

    def perform_update(self, serializer):
        # Capture old name and profile before saving
        old_name = serializer.instance.gateway
        old_profile = serializer.instance.profile or 'external'
        super().perform_update(serializer)
        new_name = serializer.instance.gateway
        new_profile = serializer.instance.profile or 'external'
        if old_name != new_name:
            _delete_gateway_file(old_name, old_profile)
        _write_gateway_file(serializer.instance)
        # Kill the old gateway registration then rescan so new config takes effect
        self._trigger_killgw_rescan(old_name, old_profile)
        if old_name != new_name or old_profile != new_profile:
            self._trigger_killgw_rescan(new_name, new_profile)

    def perform_destroy(self, instance):
        name = instance.gateway
        profile = instance.profile or 'external'
        super().perform_destroy(instance)
        _delete_gateway_file(name, profile)
        self._trigger_killgw_rescan(name, profile)

    def _trigger_killgw_rescan(self, gateway_name, profile='external'):
        """Kill gateway then rescan so config changes take effect without restarting profile."""
        try:
            from esl.tasks import sofia_killgw_and_rescan
            sofia_killgw_and_rescan.delay(gateway_name, profile)
        except Exception:
            pass  # ESL/Celery unavailable — user can run killgw + rescan manually

    def _trigger_rescan(self, profile='external'):
        """Non-disruptively rescan the Sofia profile (used for new gateways)."""
        try:
            from esl.tasks import sofia_profile_rescan
            sofia_profile_rescan.delay(profile)
        except Exception:
            pass

    @action(detail=False, methods=['post'])
    def reload(self, request):
        """Write all gateway files and rescan. Use after manual DB changes."""
        _write_all_gateway_files()
        try:
            from esl.tasks import sofia_profile_rescan
            sofia_profile_rescan.delay()
        except Exception:
            pass
        return Response({'status': 'queued'})


# ── Gateway file helpers ───────────────────────────────────────────────────────

def _gateway_dir(profile='external') -> Path:
    base = getattr(settings, 'FREESWITCH_GATEWAY_DIR',
                   '/etc/freeswitch/sip_profiles/external')
    # If profile isn't 'external', derive sibling directory
    if profile and profile != 'external':
        base = str(Path(base).parent / profile)
    return Path(base)


def _write_gateway_file(gw: Gateway):
    """Write a FreeSWITCH gateway XML include file for this gateway."""
    try:
        gw_dir = _gateway_dir(gw.profile or 'external')
        gw_dir.mkdir(parents=True, exist_ok=True)
        xml = _gateway_to_xml(gw)
        path = gw_dir / f'{gw.gateway}.xml'
        path.write_text(xml, encoding='utf-8')
        logger.info(f'Wrote gateway file: {path}')
    except Exception as e:
        logger.error(f'Failed to write gateway file for {gw.gateway}: {e}')


def _delete_gateway_file(name: str, profile: str = 'external'):
    """Remove the FreeSWITCH gateway XML include file."""
    try:
        path = _gateway_dir(profile) / f'{name}.xml'
        if path.exists():
            path.unlink()
            logger.info(f'Deleted gateway file: {path}')
    except Exception as e:
        logger.error(f'Failed to delete gateway file {name}: {e}')


def _write_all_gateway_files():
    """Write XML files for all enabled gateways (used by reload action)."""
    for gw in Gateway.objects.filter(gateway_enabled=True):
        _write_gateway_file(gw)


def _gateway_to_xml(gw: Gateway) -> str:
    """Render a gateway as a FreeSWITCH <include><gateway> XML string."""
    root = etree.Element('include')
    gw_el = etree.SubElement(root, 'gateway', name=gw.gateway)

    trunk_type = (gw.trunk_type or 'register')

    def param(name, value):
        if value:
            etree.SubElement(gw_el, 'param', name=name, value=str(value))

    if trunk_type in ('register', 'account'):
        param('username', gw.username)
        param('password', gw.password)
        if gw.auth_username:
            param('auth-username', gw.auth_username)
        if gw.realm:
            param('realm', gw.realm)

    param('proxy', gw.proxy)
    param('register-proxy', gw.register_proxy)
    param('outbound-proxy', gw.outbound_proxy)
    param('from-user', gw.from_user)
    param('from-domain', gw.from_domain)

    do_register = (trunk_type == 'register')
    etree.SubElement(gw_el, 'param', name='register',
                     value='true' if do_register else 'false')

    if do_register:
        param('register-transport', gw.register_transport or 'udp')
        etree.SubElement(gw_el, 'param', name='expire-seconds',
                         value=str(gw.expire_seconds or 3600))
        etree.SubElement(gw_el, 'param', name='retry-seconds',
                         value=str(gw.retry_seconds or 30))

    param('extension', gw.extension or 'auto_to_user')
    param('codec-prefs', gw.codec_prefs)
    # Use the channel's effective_caller_id_number in the SIP From header
    # so the provider sees a real phone number instead of the gateway username.
    etree.SubElement(gw_el, 'param', name='caller-id-in-from', value='true')

    return etree.tostring(root, pretty_print=True,
                          xml_declaration=True, encoding='UTF-8').decode()


# ── Status parser ──────────────────────────────────────────────────────────────

def _parse_gateway_states(raw: str) -> dict:
    """Parse `sofia status` text output into {gateway_name: state}.

    Example line:
        external::my-trunk   gateway   sip:user@sip.provider.com  REGED
    Known states: REGED, TRYING, FAILED, NOREG, NOAVAIL, FAIL_WAIT, UNREGED
    """
    states = {}
    if not raw:
        return states
    for line in raw.splitlines():
        # Each gateway line has at least 4 whitespace-separated columns;
        # the type column is 'gateway'.
        # Name may be "external::SIP2" — strip profile prefix to get "SIP2".
        parts = line.split()
        if len(parts) >= 4 and parts[1].lower() == 'gateway':
            name = parts[0].split('::')[-1]
            state = parts[3].upper()  # 4th column; parts[-1] breaks on "FAIL_WAIT (retry: 1s)"
            states[name] = state
    return states
