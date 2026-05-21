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
        qs = CallerExtensionAffinity.objects.all()
        user = request.user
        if not user.is_superuser:
            tenant_id = getattr(user, 'tenant_id', None)
            if not tenant_id:
                return Response({'total': 0, 'recent': []})
            qs = qs.filter(tenant_id=tenant_id)
        else:
            # Superuser: honor ?tenant=<uuid> from sidebar selection.
            tenant_id = request.query_params.get('tenant')
            if tenant_id:
                qs = qs.filter(tenant_id=tenant_id)

        total = qs.count()
        recent = qs.order_by('-last_seen')[:50]
        return Response({
            'total': total,
            'recent': CallerExtensionAffinitySerializer(recent, many=True).data,
        })
