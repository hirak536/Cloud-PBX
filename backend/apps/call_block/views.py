from rest_framework import viewsets, filters
from django_filters.rest_framework import DjangoFilterBackend
from core.mixins import TenantScopedViewSetMixin
from .models import CallBlock
from .serializers import CallBlockSerializer

class CallBlockViewSet(TenantScopedViewSetMixin, viewsets.ModelViewSet):
    queryset = CallBlock.objects.select_related('tenant', 'domain')
    serializer_class = CallBlockSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['domain', 'call_block_action', 'call_block_enabled']
    search_fields = ['call_block_number']
    ordering_fields = ['call_block_number', 'insert_date']
