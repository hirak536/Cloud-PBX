"""
FreeSWITCH Event Socket Library (ESL) client.
Wraps greenswitch for synchronous API calls and event subscriptions.
"""
import logging
import json
import re
from typing import Optional, List, Dict, Any
from django.conf import settings

logger = logging.getLogger('esl')

try:
    import greenswitch
    GREENSWITCH_AVAILABLE = True
except ImportError:
    GREENSWITCH_AVAILABLE = False
    logger.warning("greenswitch not installed. FreeSWITCH ESL disabled.")


class FreeSwitchESL:
    """
    FreeSWITCH ESL client. Connects to FreeSWITCH Event Socket.
    Usage:
        esl = FreeSwitchESL()
        result = esl.api('sofia status')
    """

    def __init__(self, host=None, port=None, password=None, timeout=None):
        self.host = host or settings.FREESWITCH_HOST
        self.port = port or settings.FREESWITCH_PORT
        self.password = password or settings.FREESWITCH_PASSWORD
        self.timeout = timeout or settings.FREESWITCH_TIMEOUT
        self._conn = None

    def _connect(self):
        if not GREENSWITCH_AVAILABLE:
            raise RuntimeError("greenswitch library not installed")
        conn = greenswitch.InboundESL(
            host=self.host,
            port=self.port,
            password=self.password,
        )
        conn.connect()
        return conn

    def api(self, command: str) -> str:
        """Execute a FreeSWITCH API command synchronously."""
        conn = self._connect()
        try:
            response = conn.send(f'api {command}\n\n')
            return response.data if hasattr(response, 'data') else str(response)
        except Exception as e:
            logger.error(f"ESL api error ({command}): {e}")
            raise
        finally:
            try:
                conn.stop()
            except Exception:
                pass

    def bgapi(self, command: str) -> str:
        """Execute a FreeSWITCH background API command (non-blocking)."""
        conn = self._connect()
        try:
            response = conn.send(f'bgapi {command}\n\n')
            return response.data if hasattr(response, 'data') else str(response)
        except Exception as e:
            logger.error(f"ESL bgapi error ({command}): {e}")
            raise
        finally:
            try:
                conn.stop()
            except Exception:
                pass

    def sendevent(self, name: str, headers: Dict[str, str], body: str = '') -> str:
        """Inject a custom event into FreeSWITCH's event system.

        Used e.g. to publish PRESENCE_IN events so BLF lamps update out-of-band
        (no active call). headers become event headers; body is the optional
        event body.
        """
        conn = self._connect()
        try:
            lines = [f'sendevent {name}']
            for k, v in headers.items():
                lines.append(f'{k}: {v}')
            payload = '\n'.join(lines) + '\n'
            if body:
                payload += f'Content-Length: {len(body)}\n\n{body}'
            response = conn.send(payload + '\n')
            return response.data if hasattr(response, 'data') else str(response)
        except Exception as e:
            logger.error(f"ESL sendevent error ({name}): {e}")
            raise
        finally:
            try:
                conn.stop()
            except Exception:
                pass

    def presence_in(self, presence_id: str, status: str = 'Active',
                    state: str = 'confirmed') -> str:
        """Publish a PRESENCE_IN event so subscribed BLF keys update.

        presence_id: the entity. For feature-code lamps this is the FusionPBX
        'flow+' form, e.g. "flow+*800@domain". The proto is the part before '+'
        ('flow'); the published login/from is the part after it ('*800@domain').
        For a plain id (no '+') proto defaults to 'sip'.
        state: 'confirmed'/'early' light the lamp (red/busy), 'terminated' clears it.

        Headers mirror FusionPBX presence_in.turn_lamp so behaviour matches the
        blf_subscribe.lua handler exactly.
        """
        userid, _, domain = presence_id.partition('@')
        if '+' in userid:
            proto, _, after = userid.partition('+')
            login = f'{after}@{domain}' if domain else after
        else:
            proto, login = 'sip', presence_id

        headers = {
            'proto': proto,
            'login': login,
            'from': login,
            'status': status,
            'event_type': 'presence',
            'alt_event_type': 'dialog',
            'Presence-Call-Direction': 'outbound',
            'answer-state': state,
            'unique-id': login,
        }
        if state == 'confirmed':
            headers['rpid'] = 'unknown'
            headers['event_count'] = '1'
        return self.sendevent('PRESENCE_IN', headers)

    def db_select(self, key: str) -> str:
        """Read a mod_db value (db select/<key>). Returns '' when unset."""
        out = self.api(f'db select/{key}')
        out = (out or '').strip()
        # FreeSWITCH returns the literal '-ERR' or empty string for a missing key.
        if not out or out.startswith('-ERR') or 'not found' in out.lower():
            return ''
        return out

    def reload_xml(self) -> str:
        """Reload FreeSWITCH XML configuration."""
        return self.api('reloadxml')

    def sofia_status(self) -> str:
        """Get Sofia SIP stack status."""
        return self.api('sofia status')

    def sofia_reload(self, profile: str = 'internal') -> str:
        """Restart a Sofia SIP profile."""
        return self.api(f'sofia profile {profile} restart')

    def sofia_rescan(self, profile: str = 'external') -> str:
        """Rescan a Sofia profile for gateway changes (non-disruptive)."""
        return self.api(f'sofia profile {profile} rescan')

    def show_calls(self) -> str:
        """Show active calls as JSON."""
        return self.api('show calls as json')

    def show_channels(self) -> str:
        """Show active channels as JSON."""
        return self.api('show channels as json')

    def show_registrations(self) -> str:
        """Show SIP registrations as JSON.

        FreeSWITCH 'show registrations as json' has a bug where it only returns
        one row per user even when multiple-registrations is enabled. We instead
        parse 'sofia status profile internal reg' which returns all registrations,
        then normalise into the same JSON rows format.
        """
        import time
        # Enumerate all enabled SIP profiles from the DB rather than a hardcoded
        # list — WebRTC devices register on the 'webrtc' profile, which was
        # previously omitted, so they never showed as online in the frontend.
        try:
            from apps.sip_profiles.models import SipProfile
            profiles = list(
                SipProfile.objects.filter(sip_profile_enabled=True)
                .values_list('sip_profile_name', flat=True)
            )
        except Exception:
            profiles = []
        # Always include the core profiles as a fallback if the DB lookup is empty.
        for default_profile in ('internal', 'external', 'webrtc'):
            if default_profile not in profiles:
                profiles.append(default_profile)
        rows = []
        seen = set()
        for profile in profiles:
            raw = self.api(f'sofia status profile {profile} reg')
            if not raw or 'Invalid Profile' in raw:
                continue
            for block in re.split(r'\n(?=Call-ID:)', raw):
                row = {}
                for line in block.splitlines():
                    line = line.strip()
                    if line.startswith('Call-ID:'):
                        row['call_id'] = line.split(':', 1)[1].strip()
                    elif line.startswith('User:'):
                        user_realm = line.split(':', 1)[1].strip()
                        row['reg_user'] = user_realm.split('@')[0]
                        row['realm'] = user_realm.split('@')[1] if '@' in user_realm else ''
                    elif line.startswith('Contact:'):
                        contact = line.split(':', 1)[1].strip()
                        row['full_contact'] = contact
                        m = re.search(r'sip:([^@]+@[^;>]+)', contact)
                        row['url'] = f'sofia/{profile}/{m.group(0)}' if m else contact
                        row.setdefault('user_agent', '')
                    elif line.startswith('Agent:'):
                        row['user_agent'] = line.split(':', 1)[1].strip()
                    elif line.startswith('IP:'):
                        row['network_ip'] = line.split(':', 1)[1].strip()
                    elif line.startswith('Port:'):
                        row['network_port'] = line.split(':', 1)[1].strip()
                    elif line.startswith('Ping-Status:'):
                        row['ping_status'] = line.split(':', 1)[1].strip()
                    elif line.startswith('Ping-Time:'):
                        # e.g. "Ping-Time: 12.345" (milliseconds)
                        val = line.split(':', 1)[1].strip()
                        try:
                            ms = int(round(float(val)))
                        except (TypeError, ValueError):
                            ms = None
                        # Sofia reports a ~32000ms sentinel (and Ping-Status: Unreachable)
                        # when the OPTIONS ping timed out with no reply — common for
                        # WebRTC clients that don't answer server OPTIONS. That's not a
                        # real RTT, so don't surface a number; the panel shows '—'.
                        if ms is None or ms >= 32000 or row.get('ping_status') == 'Unreachable':
                            row['ping_ms'] = None
                        else:
                            row['ping_ms'] = ms
                    elif line.startswith('Reg-Time:'):
                        # epoch seconds since the device registered
                        val = line.split(':', 1)[1].strip()
                        try:
                            row['registered_since'] = int(val)
                        except (TypeError, ValueError):
                            pass
                    elif line.startswith('Status:') and 'EXP(' in line:
                        m = re.search(r'EXPSECS\((\d+)\)', line)
                        if m:
                            row['expires'] = str(int(time.time()) + int(m.group(1)))
                if row.get('reg_user'):
                    row['profile'] = profile
                    key = (row['reg_user'], row.get('network_ip'), row.get('network_port'))
                    if key not in seen:
                        seen.add(key)
                        rows.append(row)
        return json.dumps({'rows': rows})

    def flush_registration(self, call_id: str, profile: str = 'internal') -> str:
        """De-register a SIP device by its Call-ID (no reboot)."""
        return self.api(f'sofia profile {profile} flush_inbound_reg {call_id}')

    def reboot_peer(self, call_id: str, profile: str = 'internal') -> str:
        """Reboot a desk phone via SIP NOTIFY check-sync.

        FreeSWITCH triggers a check-sync reboot as a side effect of
        flush_inbound_reg <call-id> reboot. The device re-registers
        after rebooting.
        """
        return self.api(f'sofia profile {profile} flush_inbound_reg {call_id} reboot')

    def show_calls_count(self) -> str:
        """Show number of active calls."""
        return self.api('show calls count')

    def originate(
        self,
        src: str,
        dst: str,
        dialplan: str = 'XML',
        context: str = 'default',
        caller_id_name: str = '',
        caller_id_number: str = '',
    ) -> str:
        """Originate a call (click-to-call)."""
        # hangup_after_bridge=true: terminate the session when the remote party hangs up
        # instead of re-entering the dialplan and re-dialing the destination.
        base_vars = 'hangup_after_bridge=true'
        if caller_id_name or caller_id_number:
            base_vars = (
                f'hangup_after_bridge=true,'
                f'origination_caller_id_name={caller_id_name},'
                f'origination_caller_id_number={caller_id_number}'
            )
        cmd = f'originate {{{base_vars}}}{src} {dst} {dialplan} {context}'
        return self.api(cmd)

    def hangup(self, uuid: str, cause: str = 'NORMAL_CLEARING') -> str:
        """Hangup a call by UUID."""
        return self.api(f'uuid_kill {uuid} {cause}')

    def transfer(
        self,
        uuid: str,
        extension: str,
        dialplan: str = 'XML',
        context: str = 'default',
    ) -> str:
        """Transfer a call to an extension."""
        return self.api(f'uuid_transfer {uuid} {extension} {dialplan} {context}')

    def hold(self, uuid: str) -> str:
        """Place a call on hold."""
        return self.api(f'uuid_hold {uuid}')

    def unhold(self, uuid: str) -> str:
        """Remove call from hold."""
        return self.api(f'uuid_hold off {uuid}')

    def uuid_getvar(self, uuid: str, var: str) -> str:
        """Get a channel variable value."""
        return self.api(f'uuid_getvar {uuid} {var}')

    def uuid_setvar(self, uuid: str, var: str, value: str) -> str:
        """Set a channel variable."""
        return self.api(f'uuid_setvar {uuid} {var} {value}')

    def eavesdrop(self, uuid: str, spy_uuid: str = '', mode: str = 'listen') -> str:
        """
        Eavesdrop on a call channel.

        mode:
          'listen'  — hear both legs, cannot speak (default)
          'whisper' — hear both legs, can speak to the called party only
          'barge'   — full three-way (both legs hear you)
        """
        mode_flag = {'listen': 'r', 'whisper': 'w', 'barge': 'rw'}.get(mode, 'r')
        if spy_uuid:
            return self.api(f'uuid_eavesdrop {spy_uuid} {uuid} {mode_flag}')
        # originate-based: caller dials feature code, FS drops them into eavesdrop
        return self.api(f'uuid_eavesdrop {uuid} all {mode_flag}')

    def conference_cmd(self, conference: str, cmd: str) -> str:
        """Send a command to a conference room."""
        return self.api(f'conference {conference} {cmd}')

    def conference_list(self) -> str:
        """List active conferences."""
        return self.api('conference list')

    def callcenter_config(self, cmd: str) -> str:
        """Call center configuration command."""
        return self.api(f'callcenter_config {cmd}')

    def gateway_killgw(self, gateway: str, profile: str = 'external') -> str:
        """Kill (unregister) a gateway so it can be re-established with new config."""
        return self.api(f'sofia profile {profile} killgw {gateway}')

    def gateway_status(self, gateway: str) -> str:
        """Check status of a SIP gateway."""
        return self.api(f'sofia status gateway {gateway}')

    def module_load(self, module: str) -> str:
        """Load a FreeSWITCH module."""
        return self.api(f'load {module}')

    def module_unload(self, module: str) -> str:
        """Unload a FreeSWITCH module."""
        return self.api(f'unload {module}')

    def module_reload(self, module: str) -> str:
        """Reload a FreeSWITCH module."""
        return self.api(f'reload {module}')

    def fs_status(self) -> str:
        """Get overall FreeSWITCH status."""
        return self.api('status')

    def version(self) -> str:
        """Get FreeSWITCH version."""
        return self.api('version')

    def global_getvar(self, var: str) -> str:
        """Get a global FreeSWITCH variable."""
        return self.api(f'global_getvar {var}')

    def global_setvar(self, var: str, value: str) -> str:
        """Set a global FreeSWITCH variable."""
        return self.api(f'global_setvar {var}={value}')

    def is_connected(self) -> bool:
        """Test connectivity to FreeSWITCH ESL."""
        try:
            result = self.version()
            return bool(result and 'FreeSWITCH' in result)
        except Exception:
            return False


# Module-level singleton factory
def get_esl_client() -> FreeSwitchESL:
    """Get a FreeSWITCH ESL client instance."""
    return FreeSwitchESL()
