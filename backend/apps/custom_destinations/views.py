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
