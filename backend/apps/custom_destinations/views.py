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
        qs = self.get_queryset().model._meta.apps.get_model(
            'custom_destinations', 'CallerExtensionAffinity'
        ).objects.all()
        # Reuse TenantScopedViewSetMixin's filter by hand: it already scoped self.queryset.
        tenant_ids = self.get_queryset().values_list('tenant_id', flat=True).distinct()
        qs = qs.filter(tenant_id__in=list(tenant_ids))

        total = qs.count()
        recent = qs.order_by('-last_seen')[:50]
        return Response({
            'total': total,
            'recent': CallerExtensionAffinitySerializer(recent, many=True).data,
        })
