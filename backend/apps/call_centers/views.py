from rest_framework import viewsets, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter
from core.mixins import TenantScopedViewSetMixin
from .models import CallCenter, CallCenterAgent, CallCenterTier
from .serializers import CallCenterSerializer, CallCenterAgentSerializer, CallCenterTierSerializer


class CallCenterViewSet(TenantScopedViewSetMixin, viewsets.ModelViewSet):
    queryset = CallCenter.objects.select_related('tenant', 'domain').prefetch_related('tiers')
    serializer_class = CallCenterSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ['enabled', 'strategy']
    search_fields = ['queue_name', 'description']

    @action(detail=True, methods=['get'])
    def status(self, request, pk=None):
        queue = self.get_object()
        try:
            from esl.client import get_esl_client
            esl = get_esl_client()
            result = esl.callcenter_config(f'queue list members {queue.queue_name}')
            return Response({'queue': queue.queue_name, 'status': result})
        except Exception as e:
            return Response({'error': str(e)}, status=503)


class CallCenterAgentViewSet(TenantScopedViewSetMixin, viewsets.ModelViewSet):
    queryset = CallCenterAgent.objects.select_related('tenant', 'domain')
    serializer_class = CallCenterAgentSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ['enabled', 'agent_type', 'agent_status']
    search_fields = ['agent_name', 'agent_contact']


class CallCenterTierViewSet(TenantScopedViewSetMixin, viewsets.ModelViewSet):
    queryset = CallCenterTier.objects.select_related('tenant', 'call_center', 'agent')
    serializer_class = CallCenterTierSerializer
    permission_classes = [permissions.IsAuthenticated]
