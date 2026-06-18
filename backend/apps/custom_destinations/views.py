from rest_framework import viewsets, permissions, mixins
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.filters import SearchFilter
from django_filters.rest_framework import DjangoFilterBackend
from core.mixins import TenantScopedViewSetMixin, write_audit_log
from .models import CustomDestination, CallerExtensionAffinity, ToggleEvent
from .serializers import (
    CustomDestinationSerializer,
    CustomDestinationListSerializer,
    CallerExtensionAffinitySerializer,
    CallerExtensionAffinityWriteSerializer,
)
from .affinity import normalize_number, upsert_affinity


class CustomDestinationViewSet(TenantScopedViewSetMixin, viewsets.ModelViewSet):
    queryset = CustomDestination.objects.select_related('tenant', 'domain')
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ['enabled', 'dest_type']
    search_fields = ['name', 'description']

    def get_serializer_class(self):
        if self.action == 'list':
            return CustomDestinationListSerializer
        return CustomDestinationSerializer

    def perform_create(self, serializer):
        super().perform_create(serializer)
        cd = serializer.instance
        if cd.kind == 'toggle' and cd.toggle_extension:
            cd.push_toggle_state()

    def perform_update(self, serializer):
        super().perform_update(serializer)
        cd = serializer.instance
        if cd.kind == 'toggle' and cd.toggle_extension:
            cd.push_toggle_state()

    @action(detail=True, methods=['get'], url_path='toggle-state')
    def toggle_state_get(self, request, pk=None):
        """Return the live ON/OFF state of a toggle, reading FreeSWITCH mod_db as
        the runtime source of truth and reconciling the DB cache if it drifted
        (e.g. after a phone-side flip the dialplan made without notifying us)."""
        cd = self.get_object()
        if cd.kind != 'toggle':
            return Response({'detail': 'Not a toggle destination.'}, status=400)
        db_state = cd.toggle_state
        live = None
        try:
            from esl.client import get_esl_client
            raw = get_esl_client().db_select(cd.toggle_db_key)
            if raw in ('true', 'false'):
                live = (raw == 'true')
        except Exception:
            live = None
        # Reconcile: trust the live runtime value when present; persist it so the
        # UI/DB stay aligned with what the phones actually show.
        if live is not None and live != db_state:
            cd.toggle_state = live
            cd.save(update_fields=['toggle_state'])
            db_state = live
        return Response({
            'custom_destination_uuid': str(cd.custom_destination_uuid),
            'state': db_state,
            'live': live,
            'source': 'freeswitch' if live is not None else 'db',
        })

    @action(detail=True, methods=['post'], url_path='set-state')
    def toggle_state_set(self, request, pk=None):
        """Set a toggle's state from the UI. Persists to the DB (source of truth)
        and pushes to FreeSWITCH (mod_db + presence) so live phone lamps update."""
        cd = self.get_object()
        if cd.kind != 'toggle':
            return Response({'detail': 'Not a toggle destination.'}, status=400)
        desired = request.data.get('state')
        if isinstance(desired, str):
            desired = desired.strip().lower() in ('true', '1', 'on', 'yes')
        if desired is None:
            desired = not cd.toggle_state  # no payload → flip
        cd.toggle_state = bool(desired)
        cd.save(update_fields=['toggle_state'])
        pushed = cd.push_toggle_state()
        # Separate audit log (these flips are deliberately kept out of the CDR).
        src = 'api' if getattr(request, 'auth', None) else 'ui'
        actor = getattr(request.user, 'username', '') or ''
        ToggleEvent.objects.create(
            custom_destination=cd, tenant=cd.tenant,
            new_state=cd.toggle_state, source=src, actor=actor,
        )
        return Response({
            'custom_destination_uuid': str(cd.custom_destination_uuid),
            'state': cd.toggle_state,
            'pushed_to_freeswitch': pushed,
        })

    @action(detail=True, methods=['get'], url_path='toggle-events')
    def toggle_events(self, request, pk=None):
        """Recent ON/OFF flips for this toggle (the separate log shown on the
        custom destination page, since these are kept out of the CDR)."""
        cd = self.get_object()
        try:
            limit = min(int(request.query_params.get('limit', 50)), 200)
        except (TypeError, ValueError):
            limit = 50
        events = cd.toggle_events.all()[:limit]
        return Response([{
            'toggle_event_uuid': str(e.toggle_event_uuid),
            'new_state': e.new_state,
            'source': e.source,
            'actor': e.actor,
            'created': e.created.isoformat(),
        } for e in events])

    @action(detail=False, methods=['post'], url_path='resync-toggles')
    def resync_toggles(self, request):
        """Republish every toggle's DB state to FreeSWITCH (mod_db + presence).

        Fixes lamp drift after a FreeSWITCH restart or phone reboot: the DB is
        the source of truth, this re-asserts it onto the runtime + phones.
        Tenant-scoped via the viewset queryset."""
        qs = self.filter_queryset(self.get_queryset()).filter(kind='toggle')
        pushed, failed = 0, 0
        for cd in qs:
            if cd.push_toggle_state():
                pushed += 1
            else:
                failed += 1
        return Response({'pushed': pushed, 'failed': failed})

    @action(detail=False, methods=['get'], url_path='affinity-stats')
    def affinity_stats(self, request):
        """Tenant-scoped affinity mappings: total count + a paginated, searchable page.

        Query params:
            search    — match caller_number (digits-normalized) or extension_number
            page      — 1-based page number (default 1)
            page_size — rows per page (default 50, max 200)
        Response keys `recent`/`total` are kept for back-compat; `total` is the
        full tenant count, `filtered_total` is the count after search.
        """
        import logging
        log = logging.getLogger(__name__)

        qs = CallerExtensionAffinity.objects.all()
        all_total = qs.count()  # diagnostic: total rows in table regardless of tenant
        user = request.user
        scoped_tenant = None

        if not user.is_superuser:
            scoped_tenant = getattr(user, 'tenant_id', None)
            if not scoped_tenant:
                log.warning('[affinity-stats] non-superuser %s has no tenant_id', user)
                return Response({'total': 0, 'filtered_total': 0, 'recent': [], 'page': 1,
                                 'page_size': 50, 'num_pages': 1,
                                 '_debug': {'all_total': all_total, 'reason': 'no tenant_id on user'}})
            qs = qs.filter(tenant_id=scoped_tenant)
        else:
            scoped_tenant = request.query_params.get('tenant')
            if scoped_tenant:
                qs = qs.filter(tenant_id=scoped_tenant)

        total = qs.count()

        # Search: match extension as-typed, or the caller number by its digits so
        # "(713) 303-4589", "7133034589", and "+1 713 303 4589" all match.
        search = (request.query_params.get('search') or '').strip()
        if search:
            from django.db.models import Q
            digits = normalize_number(search)
            cond = Q(extension_number__icontains=search)
            if digits:
                cond |= Q(caller_number__icontains=digits)
            qs = qs.filter(cond)

        filtered_total = qs.count()

        # Pagination
        try:
            page = max(1, int(request.query_params.get('page', 1)))
        except (TypeError, ValueError):
            page = 1
        try:
            page_size = min(200, max(1, int(request.query_params.get('page_size', 50))))
        except (TypeError, ValueError):
            page_size = 50
        num_pages = max(1, (filtered_total + page_size - 1) // page_size)
        start = (page - 1) * page_size
        rows = qs.order_by('-last_seen')[start:start + page_size]

        log.warning('[affinity-stats] user=%s super=%s scoped_tenant=%s all_total=%s scoped_total=%s search=%r page=%s',
                    user, user.is_superuser, scoped_tenant, all_total, total, search, page)
        return Response({
            'total': total,
            'filtered_total': filtered_total,
            'page': page,
            'page_size': page_size,
            'num_pages': num_pages,
            'recent': CallerExtensionAffinitySerializer(rows, many=True).data,
            '_debug': {'all_total': all_total, 'scoped_tenant': str(scoped_tenant), 'is_superuser': user.is_superuser},
        })

    # ── Manual affinity management ──────────────────────────────────────────────
    # Manual edits are intentionally *temporary*: the outbound-CDR signal is
    # last-write-wins, so the next outbound call from an extension to this
    # customer will overwrite a manual mapping. Surfaced in the UI accordingly.

    def _affinity_tenant(self, request):
        """Resolve the tenant a manual affinity write applies to, mirroring the
        scoping in affinity_stats. Returns a Tenant or None (caller handles 400)."""
        from core.models import Tenant
        user = request.user
        if user.is_superuser:
            tid = request.query_params.get('tenant') or request.data.get('tenant')
            return Tenant.objects.filter(tenant_uuid=tid).first() if tid else None
        return getattr(user, 'tenant', None)

    @action(detail=False, methods=['post'], url_path='affinity')
    def affinity_create(self, request):
        """Create or overwrite a manual caller→extension mapping for the tenant."""
        tenant = self._affinity_tenant(request)
        if not tenant:
            return Response({'detail': 'No tenant in scope (superusers must select one).'}, status=400)
        ser = CallerExtensionAffinityWriteSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        caller_n = normalize_number(ser.validated_data['caller_number'])
        if not caller_n:
            return Response({'detail': 'caller_number could not be normalized to a valid phone number.'}, status=400)
        # Avoid silent duplication: a number can only map to one extension. If it
        # already exists, report a conflict so the UI can offer to edit instead.
        existing = CallerExtensionAffinity.objects.filter(tenant=tenant, caller_number=caller_n).first()
        if existing and not str(request.data.get('overwrite', '')).lower() in ('1', 'true', 'yes'):
            return Response({
                'detail': f'{caller_n} is already mapped to extension {existing.extension_number}. '
                          f'Edit the existing row, or resend with overwrite=true.',
                'existing': CallerExtensionAffinitySerializer(existing).data,
            }, status=409)
        from django.utils import timezone
        domain = (tenant.domains.filter(domain_enabled=True).first()
                  if hasattr(tenant, 'domains') else None)
        obj = upsert_affinity(
            tenant=tenant, customer=caller_n,
            extension=ser.validated_data['extension_number'],
            when=timezone.now(), domain=domain, source='manual_ui',
        )
        if not obj:
            return Response({'detail': 'Could not save mapping.'}, status=400)
        write_audit_log(request, 'create', obj)
        return Response(CallerExtensionAffinitySerializer(obj).data, status=201)

    @action(detail=False, methods=['patch', 'delete'], url_path='affinity/(?P<affinity_uuid>[^/.]+)')
    def affinity_detail(self, request, affinity_uuid=None):
        """Update the extension on, or delete, one manual affinity row (tenant-scoped)."""
        tenant = self._affinity_tenant(request)
        qs = CallerExtensionAffinity.objects.all()
        if not request.user.is_superuser:
            if not tenant:
                return Response({'detail': 'No tenant in scope.'}, status=400)
            qs = qs.filter(tenant=tenant)
        elif tenant:
            qs = qs.filter(tenant=tenant)
        obj = qs.filter(affinity_uuid=affinity_uuid).first()
        if not obj:
            return Response({'detail': 'Mapping not found.'}, status=404)

        if request.method == 'DELETE':
            write_audit_log(request, 'delete', obj)
            obj.delete()
            return Response(status=204)

        ext = (request.data.get('extension_number') or '').strip()
        if not ext:
            return Response({'detail': 'extension_number is required.'}, status=400)
        from django.utils import timezone
        obj.extension_number = ext
        obj.last_seen = timezone.now()
        obj.source = 'manual_ui'
        obj.save(update_fields=['extension_number', 'last_seen', 'source', 'update_date'])
        write_audit_log(request, 'update', obj)
        return Response(CallerExtensionAffinitySerializer(obj).data)
