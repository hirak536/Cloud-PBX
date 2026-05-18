from rest_framework import viewsets, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter
from core.mixins import TenantScopedViewSetMixin
from .models import RingGroup, RingGroupDestination
from .serializers import RingGroupSerializer, RingGroupListSerializer, RingGroupDestinationSerializer


class RingGroupViewSet(TenantScopedViewSetMixin, viewsets.ModelViewSet):
    queryset = RingGroup.objects.select_related('tenant', 'domain').prefetch_related('destinations')
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        return RingGroupListSerializer if self.action == 'list' else RingGroupSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ['ring_group_enabled', 'ring_group_strategy']
    search_fields = ['ring_group_name', 'ring_group_extension']

    @action(detail=False, methods=['post'])
    def reload(self, request):
        from esl.tasks import reload_xml
        reload_xml.delay()
        return Response({'status': 'queued'})


class RingGroupDestinationViewSet(TenantScopedViewSetMixin, viewsets.ModelViewSet):
    queryset = RingGroupDestination.objects.select_related('tenant', 'domain', 'ring_group')
    serializer_class = RingGroupDestinationSerializer
    permission_classes = [permissions.IsAuthenticated]
