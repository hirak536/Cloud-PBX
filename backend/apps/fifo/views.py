from rest_framework import viewsets, filters
from django_filters.rest_framework import DjangoFilterBackend
from core.mixins import TenantScopedViewSetMixin
from .models import Fifo, FifoCallers
from .serializers import FifoSerializer, FifoListSerializer, FifoCallersSerializer

class FifoViewSet(TenantScopedViewSetMixin, viewsets.ModelViewSet):
    queryset = Fifo.objects.select_related('tenant', 'domain').prefetch_related('callers')
    serializer_class = FifoSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['domain', 'fifo_enabled']
    search_fields = ['fifo_name', 'fifo_extension']
    ordering_fields = ['fifo_name']

    def get_serializer_class(self):
        if self.action == 'list':
            return FifoListSerializer
        return FifoSerializer
