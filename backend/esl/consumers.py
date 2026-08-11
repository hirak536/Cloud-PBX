"""
Django Channels WebSocket consumers for real-time FreeSWITCH events.
Clients connect to these endpoints; a Celery worker pushes events to Redis channel layer.
"""
import json
import logging
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async

logger = logging.getLogger('esl')


class ActiveCallsConsumer(AsyncWebsocketConsumer):
    """Real-time active call events via WebSocket."""

    group_name = 'active_calls'

    async def connect(self):
        # Require authentication
        if not self.scope.get('user') or not self.scope['user'].is_authenticated:
            await self.accept()
            await self.close(code=4001)
            return
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        # Send current snapshot immediately
        await self.send_snapshot()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data):
        """Handle messages from client (e.g., hangup requests)."""
        try:
            data = json.loads(text_data)
            action = data.get('action')
            if action == 'hangup':
                uuid = data.get('uuid')
                if uuid:
                    from .client import get_esl_client
                    esl = get_esl_client()
                    result = await database_sync_to_async(esl.hangup)(uuid)
                    await self.send(json.dumps({
                        'type': 'hangup_result',
                        'uuid': uuid,
                        'result': result,
                    }))
        except Exception as e:
            logger.error(f"ActiveCallsConsumer receive error: {e}")

    async def send_snapshot(self):
        """Send current active calls snapshot."""
        try:
            from .client import get_esl_client
            from .views import (_normalize_json_rows, _connected_extension,
                                _webrtc_token_map_for, _dedupe_call_legs)
            esl = get_esl_client()
            raw = await database_sync_to_async(esl.show_calls)()
            rows = _dedupe_call_legs(_normalize_json_rows(raw))
            webrtc_map = await database_sync_to_async(_webrtc_token_map_for)(esl, rows)
            calls = [
                {
                    'uuid':     row.get('uuid', ''),
                    'cid_name': row.get('cid_name', ''),
                    'cid_num':  row.get('cid_num', ''),
                    # Final connected party, not the dialed DID/IVR/ring-group.
                    'dest':     _connected_extension(row, webrtc_map),
                    'dialed':   row.get('dest', ''),
                    'state':    row.get('callstate') or row.get('state', ''),
                    'answered': row.get('callstate') == 'ACTIVE',
                    'duration': row.get('elapsed_time', 0),
                }
                for row in rows
            ]
            await self.send(json.dumps({'type': 'active_calls_update', 'calls': calls}))
        except Exception as e:
            await self.send(json.dumps({'type': 'error', 'message': str(e)}))

    async def call_event(self, event):
        """Receive call event from channel layer and forward to WebSocket.

        The tasks send messages with keys like `event_type` and `data`.
        Transform those into the frontend-expected shape: `{ type: 'active_calls_update', calls: [...] }`.
        """
        try:
            # If the message contains a data snapshot from tasks, map to frontend shape
            if isinstance(event, dict) and 'data' in event:
                payload = {'type': 'active_calls_update', 'calls': event.get('data')}
            else:
                payload = event
            await self.send(json.dumps(payload))
        except Exception as e:
            logger.error(f"ActiveCallsConsumer call_event send error: {e}")


class ActiveConferencesConsumer(AsyncWebsocketConsumer):
    """Real-time conference events."""

    group_name = 'active_conferences'

    async def connect(self):
        if not self.scope.get('user') or not self.scope['user'].is_authenticated:
            await self.accept()
            await self.close(code=4001)
            return
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
            action = data.get('action')
            conference = data.get('conference')
            if action and conference:
                from .client import get_esl_client
                esl = get_esl_client()
                cmd = data.get('cmd', '')
                result = await database_sync_to_async(esl.conference_cmd)(conference, cmd)
                await self.send(json.dumps({
                    'type': 'conference_result',
                    'result': result,
                }))
        except Exception as e:
            logger.error(f"ActiveConferencesConsumer receive error: {e}")

    async def conference_event(self, event):
        await self.send(json.dumps(event))


class RegistrationsConsumer(AsyncWebsocketConsumer):
    """Real-time SIP registration events."""

    group_name = 'registrations'

    async def connect(self):
        if not self.scope.get('user') or not self.scope['user'].is_authenticated:
            await self.accept()
            await self.close(code=4001)
            return
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        await self.send_snapshot()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def send_snapshot(self):
        try:
            from .client import get_esl_client
            esl = get_esl_client()
            data = await database_sync_to_async(esl.show_registrations)()
            await self.send(json.dumps({'type': 'snapshot', 'data': data}))
        except Exception as e:
            await self.send(json.dumps({'type': 'error', 'message': str(e)}))

    async def registration_event(self, event):
        await self.send(json.dumps(event))


class ExtensionStatusConsumer(AsyncWebsocketConsumer):
    """
    Real-time extension presence status via WebSocket.
    Endpoint: /ws/extension-status/

    On connect: sends a full snapshot of all known extension statuses.
    Ongoing: receives push updates from the `extension_status` Redis group
             whenever a Celery task detects a registration or call-state change.

    Message formats sent to the client:
      Snapshot : { "type": "extension_status_snapshot", "extensions": { "1001": "online", ... } }
      Update   : { "type": "extension_status_update",   "extension": "1001", "status": "ringing" }
    """

    group_name = 'extension_status'

    def _get_tenant_code(self):
        """Return tenant_code for the connected user, or None for superusers/staff."""
        user = self.scope.get('user')
        if not user or user.is_superuser or user.is_staff:
            return None
        tenant = getattr(user, 'tenant', None)
        return tenant.tenant_code if tenant else None

    async def connect(self):
        if not self.scope.get('user') or not self.scope['user'].is_authenticated:
            await self.accept()
            await self.close(code=4001)
            return
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        await self.send_snapshot()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data):
        pass  # read-only consumer

    async def send_snapshot(self):
        """Derive and send a full extension-status snapshot on connect."""
        try:
            from .tasks import _build_extension_status_map
            status_map = await database_sync_to_async(_build_extension_status_map)()
            tenant_code = self._get_tenant_code()
            if tenant_code:
                from apps.extensions.models import Extension
                tenant_exts = await database_sync_to_async(
                    lambda: set(
                        Extension.objects.filter(
                            tenant__tenant_code=tenant_code, enabled=True
                        ).values_list('sip_username', flat=True)
                    )
                )()
                status_map = {k: v for k, v in status_map.items() if k in tenant_exts}
            await self.send(json.dumps({
                'type': 'extension_status_snapshot',
                'extensions': status_map,
            }))
        except Exception as e:
            logger.error(f"ExtensionStatusConsumer send_snapshot error: {e}")
            await self.send(json.dumps({'type': 'error', 'message': str(e)}))

    async def extension_status_event(self, event):
        """Forward channel-layer messages to the WebSocket client."""
        try:
            payload = event.get('payload', event)
            tenant_code = self._get_tenant_code()
            if tenant_code and isinstance(payload, dict) and 'extensions' in payload:
                from apps.extensions.models import Extension
                tenant_exts = await database_sync_to_async(
                    lambda: set(
                        Extension.objects.filter(
                            tenant__tenant_code=tenant_code, enabled=True
                        ).values_list('sip_username', flat=True)
                    )
                )()
                payload = {
                    **payload,
                    'extensions': {k: v for k, v in payload['extensions'].items() if k in tenant_exts},
                }
            await self.send(json.dumps(payload))
        except Exception as e:
            logger.error(f"ExtensionStatusConsumer extension_status_event error: {e}")


class OperatorPanelConsumer(AsyncWebsocketConsumer):
    """Full operator panel - active calls + registrations combined."""

    group_name = 'operator_panel'

    def _get_superuser_tenant_uuid(self):
        """Return the ?tenant=<uuid> query param value if the user is a superuser/staff, else None."""
        user = self.scope.get('user')
        if not user or not (user.is_superuser or user.is_staff):
            return None
        from urllib.parse import parse_qs
        qs = self.scope.get('query_string', b'').decode()
        params = parse_qs(qs)
        return (params.get('tenant') or [None])[0]

    def _get_tenant_code(self):
        """Return tenant_code for the connected user.
        Superusers/staff are scoped via the ?tenant=<uuid> query param (same as the REST API).
        Returns None only when no tenant context exists (superuser with no param = all calls)."""
        user = self.scope.get('user')
        if not user:
            return None
        if user.is_superuser or user.is_staff:
            # Superuser tenant code is resolved asynchronously via _resolve_superuser_tenant_code();
            # this sync method returns None for superusers — callers that need filtering must use
            # the async version instead.
            return None
        tenant = getattr(user, 'tenant', None)
        return tenant.tenant_code if tenant else None

    async def _resolve_tenant_code(self):
        """Async version of _get_tenant_code() — resolves superuser tenant via DB lookup."""
        user = self.scope.get('user')
        if not user:
            return None
        if user.is_superuser or user.is_staff:
            tenant_uuid = self._get_superuser_tenant_uuid()
            if not tenant_uuid:
                return None
            from core.models import Tenant
            t = await database_sync_to_async(
                lambda: Tenant.objects.filter(tenant_uuid=tenant_uuid).first()
            )()
            return t.tenant_code if t else None
        tenant = getattr(user, 'tenant', None)
        return tenant.tenant_code if tenant else None

    def _filter_calls(self, calls, tenant_code, rg_extensions=None):
        """Filter call list to the given tenant. Returns all if tenant_code is None."""
        if not tenant_code:
            return calls
        suffix = f'-{tenant_code}'
        rg_exts = rg_extensions or set()
        # 'dest' is the connected extension and 'dialed' the originally dialed
        # number; check both so a call still matches whether it is already
        # bridged to an extension or still sitting in an IVR/ring group.
        return [
            c for c in calls
            if str(c.get('cid_num', '')).endswith(suffix) or
               str(c.get('dest', '')).endswith(suffix) or
               str(c.get('dialed', '')).endswith(suffix) or
               str(c.get('dest', '')) in rg_exts or
               str(c.get('dialed', '')) in rg_exts
        ]

    async def _get_tenant_ring_group_extensions(self, tenant_code):
        """Return the set of ring group extensions belonging to the given tenant."""
        if not tenant_code:
            return set()
        from apps.ring_groups.models import RingGroup
        return await database_sync_to_async(
            lambda: set(
                RingGroup.objects.filter(
                    tenant__tenant_code=tenant_code, ring_group_enabled=True
                ).values_list('ring_group_extension', flat=True)
            )
        )()

    def _filter_regs(self, regs, tenant_code):
        """Filter registration list to the given tenant. Returns all if tenant_code is None."""
        if not tenant_code:
            return regs
        suffix = f'-{tenant_code}'
        return [
            r for r in regs
            if str(r.get('user', '') or r.get('reg_user', '')).endswith(suffix)
        ]

    async def connect(self):
        if not self.scope.get('user') or not self.scope['user'].is_authenticated:
            await self.accept()
            await self.close(code=4001)
            return
        # Subscribe to groups for calls, registrations, system metrics, freeswitch and DB status
        await self.channel_layer.group_add('active_calls', self.channel_name)
        await self.channel_layer.group_add('registrations', self.channel_name)
        await self.channel_layer.group_add('system_metrics', self.channel_name)
        await self.channel_layer.group_add('freeswitch_status', self.channel_name)
        await self.channel_layer.group_add('db_status', self.channel_name)
        await self.channel_layer.group_add('extension_status', self.channel_name)
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        await self.send_extension_status_snapshot()
        await self.send_calls_snapshot()
        await self.send_registrations_snapshot()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard('active_calls', self.channel_name)
        await self.channel_layer.group_discard('registrations', self.channel_name)
        await self.channel_layer.group_discard('system_metrics', self.channel_name)
        await self.channel_layer.group_discard('freeswitch_status', self.channel_name)
        await self.channel_layer.group_discard('db_status', self.channel_name)
        await self.channel_layer.group_discard('extension_status', self.channel_name)
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data):
        pass  # Operator panel is read-only

    async def call_event(self, event):
        try:
            if isinstance(event, dict) and 'data' in event:
                tenant_code = await self._resolve_tenant_code()
                rg_exts = await self._get_tenant_ring_group_extensions(tenant_code)
                calls = self._filter_calls(event.get('data') or [], tenant_code, rg_extensions=rg_exts)
                payload = {'type': 'active_calls_update', 'calls': calls}
            else:
                payload = event
            await self.send(json.dumps(payload))
        except Exception as e:
            logger.error(f"OperatorPanelConsumer call_event send error: {e}")

    async def operator_event(self, event):
        await self.send(json.dumps(event))

    async def registration_event(self, event):
        try:
            if isinstance(event, dict) and 'data' in event:
                tenant_code = await self._resolve_tenant_code()
                regs = self._filter_regs(event.get('data') or [], tenant_code)
                payload = {'type': 'registrations_update', 'registrations': regs}
            else:
                payload = event
            await self.send(json.dumps(payload))
        except Exception as e:
            logger.error(f"OperatorPanelConsumer registration_event error: {e}")

    async def system_metrics_event(self, event):
        try:
            if isinstance(event, dict) and 'data' in event:
                payload = {'type': 'system_metrics', 'metrics': event.get('data')}
            else:
                payload = event
            await self.send(json.dumps(payload))
        except Exception as e:
            logger.error(f"OperatorPanelConsumer system_metrics_event error: {e}")

    async def freeswitch_status_event(self, event):
        try:
            if isinstance(event, dict) and 'data' in event:
                payload = {'type': 'freeswitch_status', 'status': event.get('data')}
            else:
                payload = event
            await self.send(json.dumps(payload))
        except Exception as e:
            logger.error(f"OperatorPanelConsumer freeswitch_status_event error: {e}")

    async def db_status_event(self, event):
        try:
            if isinstance(event, dict) and 'data' in event:
                payload = {'type': 'db_status', 'status': event.get('data')}
            else:
                payload = event
            await self.send(json.dumps(payload))
        except Exception as e:
            logger.error(f"OperatorPanelConsumer db_status_event error: {e}")

    async def send_calls_snapshot(self):
        try:
            from .client import get_esl_client
            from .views import (_normalize_json_rows, _connected_extension,
                                _webrtc_token_map_for, _dedupe_call_legs)
            esl = get_esl_client()
            raw = await database_sync_to_async(esl.show_calls)()
            rows = _dedupe_call_legs(_normalize_json_rows(raw))
            webrtc_map = await database_sync_to_async(_webrtc_token_map_for)(esl, rows)
            calls = [
                {
                    'uuid':     row.get('uuid', ''),
                    'cid_name': row.get('cid_name', ''),
                    'cid_num':  row.get('cid_num', ''),
                    # Final connected party, not the dialed DID/IVR/ring-group.
                    'dest':     _connected_extension(row, webrtc_map),
                    'dialed':   row.get('dest', ''),
                    'state':    row.get('callstate') or row.get('state', ''),
                    'answered': row.get('callstate') == 'ACTIVE',
                    'duration': row.get('elapsed_time', 0),
                }
                for row in rows
            ]
            tenant_code = await self._resolve_tenant_code()
            rg_exts = await self._get_tenant_ring_group_extensions(tenant_code)
            calls = self._filter_calls(calls, tenant_code, rg_extensions=rg_exts)
            await self.send(json.dumps({'type': 'active_calls_update', 'calls': calls}))
        except Exception as e:
            logger.error(f"OperatorPanelConsumer send_calls_snapshot error: {e}")

    async def send_registrations_snapshot(self):
        try:
            from .client import get_esl_client
            esl = get_esl_client()
            raw = await database_sync_to_async(esl.show_registrations)()
            rows = json.loads(raw).get('rows', []) if isinstance(raw, str) else raw.get('rows', [])
            tenant_code = await self._resolve_tenant_code()
            regs = self._filter_regs(rows, tenant_code)
            await self.send(json.dumps({'type': 'registrations_update', 'registrations': regs}))
        except Exception as e:
            logger.error(f"OperatorPanelConsumer send_registrations_snapshot error: {e}")

    async def send_extension_status_snapshot(self):
        try:
            from .tasks import _build_extension_status_map
            status_map = await database_sync_to_async(_build_extension_status_map)()
            tenant_code = await self._resolve_tenant_code()
            if tenant_code:
                from apps.extensions.models import Extension
                tenant_exts = await database_sync_to_async(
                    lambda: set(
                        Extension.objects.filter(
                            tenant__tenant_code=tenant_code, enabled=True
                        ).values_list('sip_username', flat=True)
                    )
                )()
                status_map = {k: v for k, v in status_map.items() if k in tenant_exts}
            await self.send(json.dumps({
                'type': 'extension_status_snapshot',
                'extensions': status_map,
            }))
        except Exception as e:
            logger.error(f"OperatorPanelConsumer send_extension_status_snapshot error: {e}")

    async def extension_status_event(self, event):
        try:
            payload = event.get('payload', event)
            tenant_code = await self._resolve_tenant_code()
            if tenant_code and isinstance(payload, dict) and 'extensions' in payload:
                from apps.extensions.models import Extension
                tenant_exts = await database_sync_to_async(
                    lambda: set(
                        Extension.objects.filter(
                            tenant__tenant_code=tenant_code, enabled=True
                        ).values_list('sip_username', flat=True)
                    )
                )()
                payload = {
                    **payload,
                    'extensions': {k: v for k, v in payload['extensions'].items() if k in tenant_exts},
                }
            await self.send(json.dumps(payload))
        except Exception as e:
            logger.error(f"OperatorPanelConsumer extension_status_event error: {e}")
