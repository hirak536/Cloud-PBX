from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from core.mixins import TenantScopedViewSetMixin
from .models import CallParkingSlot
from .serializers import CallParkingSlotSerializer, CallParkingSlotListSerializer, BulkCreateSerializer


class CallParkingSlotViewSet(TenantScopedViewSetMixin, viewsets.ModelViewSet):
    queryset = CallParkingSlot.objects.select_related('tenant', 'domain')
    permission_classes = [permissions.IsAuthenticated]
    cache_timeout = 0  # parking slots are low-traffic; skip caching to avoid stale list
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['slot_enabled']
    search_fields = ['slot_name']
    ordering_fields = ['slot_number', 'slot_name']
    ordering = ['slot_number']

    def get_serializer_class(self):
        return (
            CallParkingSlotListSerializer
            if self.action == 'list'
            else CallParkingSlotSerializer
        )

    @action(detail=False, methods=['post'])
    def bulk_create(self, request):
        """Create one slot per number in slot_start..slot_end range."""
        ser = BulkCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data

        # Resolve tenant the same way TenantScopedViewSetMixin.perform_create does
        tenant = None
        if request.user.is_superuser:
            tenant_id = request.query_params.get('tenant')
            if tenant_id:
                from core.models import Tenant
                tenant = Tenant.objects.filter(tenant_uuid=tenant_id).first()
        if not tenant:
            tenant = getattr(request.user, 'tenant', None)

        domain = getattr(request.user, 'domain', None)
        if not domain:
            from core.models import Domain
            domain = Domain.objects.filter(domain_universal=True, domain_enabled=True).first()

        existing = set(
            CallParkingSlot.objects.filter(tenant=tenant)
            .values_list('slot_number', flat=True)
        )
        created, skipped = [], []
        for n in range(d['slot_start'], d['slot_end'] + 1):
            if n in existing:
                skipped.append(n)
                continue
            CallParkingSlot.objects.create(
                tenant=tenant,
                domain=domain,
                slot_number=n,
                parking_timeout=d['parking_timeout'],
                timeout_action=d['timeout_action'],
                timeout_voicemail_extension=d['timeout_voicemail_extension'],
                music_on_hold=d['music_on_hold'],
                slot_enabled=d['slot_enabled'],
            )
            created.append(n)

        return Response({'created': created, 'skipped': skipped}, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['post'])
    def reload(self, request):
        from esl.tasks import reload_xml
        reload_xml.delay()
        return Response({'status': 'queued'})
