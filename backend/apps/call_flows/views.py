from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from core.mixins import TenantScopedViewSetMixin
from .models import CallFlow, CallFlowOption
from .serializers import CallFlowSerializer, CallFlowListSerializer, CallFlowOptionSerializer

class CallFlowViewSet(TenantScopedViewSetMixin, viewsets.ModelViewSet):
    queryset = CallFlow.objects.select_related('tenant', 'domain').prefetch_related('options')
    serializer_class = CallFlowSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['domain', 'call_flow_enabled']
    search_fields = ['call_flow_name', 'call_flow_extension']
    ordering_fields = ['call_flow_name']

    def get_serializer_class(self):
        if self.action == 'list':
            return CallFlowListSerializer
        return CallFlowSerializer

    @action(detail=True, methods=['post'])
    def toggle(self, request, pk=None):
        cf = self.get_object()
        cf.call_flow_status = 'false' if cf.call_flow_status == 'true' else 'true'
        cf.save(update_fields=['call_flow_status'])
        return Response({'status': cf.call_flow_status})

class CallFlowOptionViewSet(TenantScopedViewSetMixin, viewsets.ModelViewSet):
    queryset = CallFlowOption.objects.select_related('tenant', 'domain')
    serializer_class = CallFlowOptionSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['call_flow']
