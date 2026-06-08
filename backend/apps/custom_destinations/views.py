from rest_framework import viewsets, permissions, mixins
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.filters import SearchFilter
from django_filters.rest_framework import DjangoFilterBackend
from core.mixins import TenantScopedViewSetMixin
from .models import CustomDestination, CallerExtensionAffinity
from .serializers import (
    CustomDestinationSerializer,
    CustomDestinationListSerializer,
    CallerExtensionAffinitySerializer,
)


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
        cd = serializer.save()
        if cd.kind == 'toggle' and cd.toggle_extension:
            cd.push_toggle_state()

    def perform_update(self, serializer):
        cd = serializer.save()
        # Re-assert state onto FreeSWITCH after any edit so the lamp matches the
        # saved record (and a renamed/renumbered toggle re-publishes correctly).
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
        return Response({
            'custom_destination_uuid': str(cd.custom_destination_uuid),
            'state': cd.toggle_state,
            'pushed_to_freeswitch': pushed,
        })

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
        """Tenant-scoped count + most-recent affinity mappings."""
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
                return Response({'total': 0, 'recent': [], '_debug': {'all_total': all_total, 'reason': 'no tenant_id on user'}})
            qs = qs.filter(tenant_id=scoped_tenant)
        else:
            scoped_tenant = request.query_params.get('tenant')
            if scoped_tenant:
                qs = qs.filter(tenant_id=scoped_tenant)

        total = qs.count()
        log.warning('[affinity-stats] user=%s super=%s scoped_tenant=%s all_total=%s scoped_total=%s',
                    user, user.is_superuser, scoped_tenant, all_total, total)
        recent = qs.order_by('-last_seen')[:50]
        return Response({
            'total': total,
            'recent': CallerExtensionAffinitySerializer(recent, many=True).data,
            '_debug': {'all_total': all_total, 'scoped_tenant': str(scoped_tenant), 'is_superuser': user.is_superuser},
        })
