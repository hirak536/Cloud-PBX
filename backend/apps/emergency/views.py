from rest_framework import viewsets, filters
from django_filters.rest_framework import DjangoFilterBackend
from core.mixins import TenantScopedViewSetMixin
from .models import Emergency
from .serializers import EmergencySerializer

class EmergencyViewSet(TenantScopedViewSetMixin, viewsets.ModelViewSet):
    queryset = Emergency.objects.select_related('tenant', 'domain')
    serializer_class = EmergencySerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['domain', 'emergency_enabled']
    search_fields = ['emergency_number', 'emergency_destination']
