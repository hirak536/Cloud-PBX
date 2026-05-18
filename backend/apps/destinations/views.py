from django.db.models import Q
from rest_framework import viewsets, filters
from django_filters.rest_framework import DjangoFilterBackend
from core.mixins import TenantScopedViewSetMixin
from .models import Destination
from .serializers import DestinationSerializer, DestinationListSerializer

class DestinationViewSet(TenantScopedViewSetMixin, viewsets.ModelViewSet):
    queryset = Destination.objects.select_related('tenant', 'domain', 'domain__tenant').prefetch_related('actions')
    serializer_class = DestinationSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['domain', 'dest_type', 'destination_enabled', 'fax']
    search_fields = ['destination_number', 'destination_name', 'destination_description']
    ordering_fields = ['destination_number', 'destination_name', 'dest_type', 'insert_date']

    def get_serializer_class(self):
        if self.action == 'list':
            return DestinationListSerializer
        return DestinationSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        # ?fax_enabled=true → destinations with a fax box linked OR dest_type=fax
        if self.request.query_params.get('fax_enabled') == 'true':
            qs = qs.filter(Q(fax__isnull=False) | Q(dest_type='fax'))
        return qs
