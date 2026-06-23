import csv
from django.http import HttpResponse
from django.db.models import Count, Sum, Avg, Q
from rest_framework import viewsets, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from core.mixins import TenantScopedViewSetMixin
from .models import XmlCdr
from .serializers import XmlCdrSerializer


class XmlCdrViewSet(TenantScopedViewSetMixin, viewsets.ReadOnlyModelViewSet):
    # Read from denormalized tenant/domain columns (no FK join) so the queryset
    # works unchanged once CDRs move to a separate DB.
    queryset = XmlCdr.objects.all()
    serializer_class = XmlCdrSerializer
    permission_classes = [permissions.IsAuthenticated]
    cache_timeout = 0  # Disable caching — CDRs update frequently
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['direction', 'hangup_cause', 'missed_call', 'leg']
    search_fields = ['caller_id_number', 'caller_id_name', 'destination_number']
    ordering_fields = ['start_stamp', 'duration', 'billsec', 'insert_date']
    ordering = ['-start_stamp']

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        # Extensions whose no-answer routing lands on voicemail — a missed call to
        # one of these is reported as voicemail across every CDR API. The admin list
        # spans tenants, so the lookup is global; identifiers are mostly the
        # tenant-suffixed sip_username form ("906-IHDT"), which is unique per tenant.
        from apps.common.vm_routing import vm_route_idents  # noqa: PLC0415
        ctx['vm_route_idents'] = vm_route_idents()
        return ctx

    def get_queryset(self):
        # Scope by the denormalized tenant_uuid_val column rather than the FK, so
        # this never joins to core.* (works once CDRs live in a separate DB). This
        # intentionally replaces the mixin's FK-based get_queryset, mirroring its
        # superuser (?tenant=<uuid>) and per-user scoping rules.
        qs = XmlCdr.objects.all()
        user = self.request.user
        if user.is_superuser:
            tenant_id = self.request.query_params.get('tenant')
            if tenant_id:
                qs = qs.filter(tenant_uuid_val=tenant_id)
            # else: all tenants
        else:
            tenant_id = getattr(user, 'tenant_id', None)
            if tenant_id:
                qs = qs.filter(tenant_uuid_val=tenant_id)
            else:
                qs = qs.none()
        # Restrict to the A-leg so each call appears once. Without this the list and
        # summary double-count (every call has both an A-leg and B-leg row), which is
        # what makes the admin CDR view disagree with the client_api view.
        qs = qs.filter(leg='a')
        p = self.request.query_params
        # Accept both naming conventions (frontend sends __gte/__lte; legacy uses start_date/end_date)
        start = p.get('start_stamp__gte') or p.get('start_date')
        end = p.get('start_stamp__lte') or p.get('end_date')
        if start:
            qs = qs.filter(start_stamp__gte=start)
        if end:
            qs = qs.filter(start_stamp__lte=end)
        return qs

    @action(detail=True, methods=['get'])
    def legs(self, request, pk=None):
        # Per-member leg breakdown for a call (e.g. each extension a ring group
        # forked to). The B-legs are linked to this A-leg by bridge_uuid == call_uuid.
        # Tenant scoping is inherited via get_queryset() on the detail lookup.
        a_leg = self.get_object()
        if not a_leg.call_uuid:
            return Response([])
        legs = (
            XmlCdr.objects
            .filter(bridge_uuid=a_leg.call_uuid, leg='b')
            .order_by('start_stamp')
        )
        ser = self.get_serializer(legs, many=True)
        return Response(ser.data)

    def _ordered_legs(self, a_leg):
        """A-leg followed by its B-legs, ordered as the UI groups them
        ('First Leg' then 'Second Leg 0..N'). Mirrors the `legs` action."""
        legs = [('First Leg', a_leg)]
        if a_leg.call_uuid:
            b_legs = (
                XmlCdr.objects
                .filter(bridge_uuid=a_leg.call_uuid, leg='b')
                .order_by('start_stamp')
            )
            for i, b in enumerate(b_legs):
                legs.append((f'Second Leg {i}', b))
        return legs

    @action(detail=True, methods=['get'])
    def pcap(self, request, pk=None):
        """Per-leg SIP frame summary (tshark-style) sliced from the rolling
        SIP capture, grouped by leg exactly like the CDR expander."""
        from .sip_capture import leg_sip_view, CaptureUnavailable  # noqa: PLC0415
        a_leg = self.get_object()  # tenant-scoped via get_queryset
        out = []
        capture_present = True
        for label, leg in self._ordered_legs(a_leg):
            from .tasks import NO_CAPTURE_SENTINEL  # noqa: PLC0415
            if not leg.sip_call_id:
                out.append({
                    'label': label, 'leg_uuid': str(leg.xml_cdr_uuid),
                    'call_id': '', 'frames': [], 'available': False,
                    'reason': 'No SIP Call-ID recorded for this leg.',
                })
                continue
            # Known no-capture (the background sweep already tried and found no
            # packets — almost always a scanner call we don't capture). Don't
            # waste a live scan; report it directly.
            if leg.sip_pcap_path == NO_CAPTURE_SENTINEL:
                out.append({
                    'label': label, 'leg_uuid': str(leg.xml_cdr_uuid),
                    'call_id': leg.sip_call_id, 'frames': [], 'available': False,
                    'reason': 'No captured packets for this leg (not a captured peer, or rotated out).',
                })
                continue
            try:
                frames, has_capture = leg_sip_view(
                    leg.sip_call_id, leg.start_stamp, leg.end_stamp,
                    presliced_path=leg.sip_pcap_path or None,
                    presliced_bytes=(bytes(leg.sip_pcap_data) if leg.sip_pcap_data else None),
                )
            except CaptureUnavailable as e:
                capture_present = False
                frames, has_capture = [], False
                reason = str(e)
            else:
                reason = None if has_capture else 'No captured packets found for this leg (call predates capture, or rotated out).'
            out.append({
                'label': label, 'leg_uuid': str(leg.xml_cdr_uuid),
                'call_id': leg.sip_call_id, 'frames': frames,
                'available': has_capture, 'reason': reason,
            })
        return Response({'legs': out, 'capture_enabled': capture_present})

    @action(detail=True, methods=['get'], url_path='pcap/(?P<leg_uuid>[^/.]+)/download')
    def pcap_download(self, request, pk=None, leg_uuid=None):
        """Download the raw per-leg .pcap (openable in sngrep/Wireshark)."""
        import os, tempfile  # noqa: PLC0415
        from .sip_capture import slice_leg_pcap, CaptureUnavailable  # noqa: PLC0415
        a_leg = self.get_object()
        leg = next((l for _, l in self._ordered_legs(a_leg)
                    if str(l.xml_cdr_uuid) == leg_uuid), None)
        if leg is None or not leg.sip_call_id:
            return Response({'detail': 'Leg not found or has no SIP Call-ID.'}, status=404)
        # Fastest path: packets stored in the DB row.
        if leg.sip_pcap_data:
            data = bytes(leg.sip_pcap_data)
        # Fallback: pre-sliced file on disk (oversize case).
        elif leg.sip_pcap_path and leg.sip_pcap_path != 'none' and os.path.exists(leg.sip_pcap_path):
            with open(leg.sip_pcap_path, 'rb') as fh:
                data = fh.read()
        else:
            with tempfile.NamedTemporaryFile(suffix='.pcap', delete=False) as tmp:
                tmp_path = tmp.name
            try:
                sliced = slice_leg_pcap(leg.sip_call_id, leg.start_stamp, leg.end_stamp, tmp_path)
            except CaptureUnavailable as e:
                return Response({'detail': str(e)}, status=503)
            if not sliced:
                return Response({'detail': 'No captured packets for this leg.'}, status=404)
            with open(sliced, 'rb') as fh:
                data = fh.read()
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
        resp = HttpResponse(data, content_type='application/vnd.tcpdump.pcap')
        resp['Content-Disposition'] = f'attachment; filename="leg-{leg_uuid}.pcap"'
        return resp

    @action(detail=False, methods=['get'])
    def summary(self, request):
        qs = self.get_queryset()
        total = qs.count()
        answered = qs.filter(billsec__gt=0).count()
        data = qs.aggregate(
            total_duration=Sum('duration'),
            total_billsec=Sum('billsec'),
            avg_duration=Avg('duration'),
        )
        return Response({
            'total_calls': total,
            'answered_calls': answered,
            'missed_calls': total - answered,
            'answer_rate': round(answered / total * 100, 1) if total else 0,
            'total_duration': data['total_duration'] or 0,
            'total_billsec': data['total_billsec'] or 0,
            'avg_duration': round(data['avg_duration'] or 0, 1),
        })

    @action(detail=False, methods=['get'], url_path='homer-search')
    def homer_search(self, request):
        """Tenant-scoped search over HOMER-captured SIP.

        Query params:
          Time window (pick one): from&to (ISO) | date=YYYY-MM-DD | date_from&date_to
          number     — substring match on caller/callee
          extension  — exact match on an extension (bare + tenant-suffixed forms)
          call_id    — exact Call-ID
          tenant     — superadmin only: narrow to one tenant_uuid
          page       — 1-based page number (default 1)
          page_size  — results per page (default 20, max 100)
        Tenant users are hard-scoped to their own tenant; superadmins see all
        tenants plus the unattributed bucket. Returns correlated call rows.
        """
        from datetime import datetime, timedelta, timezone as _tz  # noqa: PLC0415
        from django.utils import timezone  # noqa: PLC0415
        from django.utils.dateparse import parse_datetime, parse_date  # noqa: PLC0415
        from .homer_search import search_calls  # noqa: PLC0415

        now = timezone.now()
        qp = request.query_params

        def _day_start(d):
            return datetime(d.year, d.month, d.day, tzinfo=_tz.utc)

        def _parse_dt(s):
            """Accept a full datetime OR a bare date (treated as that day's 00:00 UTC)."""
            if not s:
                return None
            dtv = parse_datetime(s)
            if dtv is not None:
                return dtv if dtv.tzinfo else dtv.replace(tzinfo=_tz.utc)
            d = parse_date(s)
            return _day_start(d) if d else None

        if qp.get('from') or qp.get('to'):
            ws = _parse_dt(qp.get('from', '')) or (now - timedelta(hours=24))
            we = _parse_dt(qp.get('to', '')) or now
        elif qp.get('date'):
            d = parse_date(qp['date'])
            ws = _day_start(d)
            we = ws + timedelta(days=1)
        elif qp.get('date_from') or qp.get('date_to'):
            df = parse_date(qp.get('date_from', '')) or (now - timedelta(days=1)).date()
            dt = parse_date(qp.get('date_to', '')) or now.date()
            ws = _day_start(df)
            we = _day_start(dt) + timedelta(days=1)
        else:
            ws, we = now - timedelta(hours=24), now

        number = qp.get('number', '').strip()
        extension = qp.get('extension', '').strip()
        call_id = qp.get('call_id', '').strip()

        user = request.user
        is_superadmin = bool(user.is_superuser)
        if is_superadmin:
            tenant_id = qp.get('tenant') or None
        else:
            tenant_id = str(getattr(user, 'tenant_id', '') or '')
            if not tenant_id:
                return Response({'results': [], 'page': 1, 'page_size': 20,
                                 'count': 0, 'total': 0, 'has_more': False})

        try:
            page = max(int(qp.get('page', 1)), 1)
        except (TypeError, ValueError):
            page = 1
        try:
            page_size = min(max(int(qp.get('page_size', 20)), 1), 100)
        except (TypeError, ValueError):
            page_size = 20

        fetch = min(page * page_size, 500)
        results = search_calls(
            ws, we, tenant_id=tenant_id, is_superadmin=is_superadmin,
            number=number, extension=extension, call_id=call_id,
            group='leg' if qp.get('group') == 'leg' else 'call', limit=fetch,
        )
        total = len(results)
        start = (page - 1) * page_size
        page_items = results[start:start + page_size]
        return Response({
            'results': page_items,
            'page': page,
            'page_size': page_size,
            'count': len(page_items),
            'total': total,
            'has_more': (start + page_size) < total,
            'window': {'from': ws.isoformat(), 'to': we.isoformat()},
        })

    @action(detail=False, methods=['get'], url_path='homer-ladder')
    def homer_ladder(self, request):
        """Decoded SIP ladder for one Call-ID, tenant-scoped (frames per leg).

        Params: call_id (required), from/to (window; default last 24h).
        Authorizes that the Call-ID attributes to the caller's tenant before
        decoding — a tenant user cannot pull another tenant's signaling.
        """
        from datetime import timedelta  # noqa: PLC0415
        from django.utils import timezone  # noqa: PLC0415
        from django.utils.dateparse import parse_datetime, parse_date  # noqa: PLC0415
        from .homer_search import search_calls  # noqa: PLC0415
        from .sip_capture import leg_sip_view  # noqa: PLC0415

        call_id = request.query_params.get('call_id', '').strip()
        if not call_id:
            return Response({'detail': 'call_id is required.'}, status=400)
        now = timezone.now()
        ws = (parse_datetime(request.query_params.get('from', '')) or
              (parse_date(request.query_params.get('from', '')) and
               timezone.make_aware(timezone.datetime.combine(parse_date(request.query_params['from']), timezone.datetime.min.time()))) or
              now - timedelta(hours=24))
        we = parse_datetime(request.query_params.get('to', '')) or now

        user = request.user
        is_superadmin = bool(user.is_superuser)
        tenant_id = (request.query_params.get('tenant') or None) if is_superadmin \
            else str(getattr(user, 'tenant_id', '') or '')
        if not is_superadmin and not tenant_id:
            return Response({'detail': 'No tenant.'}, status=403)

        owned = search_calls(ws, we, tenant_id=tenant_id, is_superadmin=is_superadmin,
                             call_id=call_id, group='leg', limit=1)
        if not owned:
            return Response({'detail': 'Call-ID not found for this tenant in the window.'},
                            status=404)

        frames, has_capture = leg_sip_view(call_id, ws, we)
        return Response({'call_id': call_id, 'has_capture': has_capture, 'frames': frames})

    @action(detail=False, methods=['get'])
    def export(self, request):
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="cdr.csv"'
        w = csv.writer(response)
        w.writerow(['Start Time','Caller ID','Caller Name','Destination','Duration','Billsec',
                    'Hangup Cause','Direction','Context'])
        for cdr in self.get_queryset()[:10000]:
            w.writerow([cdr.start_stamp, cdr.caller_id_number, cdr.caller_id_name,
                        cdr.destination_number, cdr.duration, cdr.billsec,
                        cdr.hangup_cause, cdr.direction, cdr.context])
        return response
