from rest_framework import viewsets, filters
from django_filters.rest_framework import DjangoFilterBackend
from core.mixins import TenantScopedViewSetMixin
from .models import EventGuard
from .serializers import EventGuardSerializer

class EventGuardViewSet(TenantScopedViewSetMixin, viewsets.ModelViewSet):
    queryset = EventGuard.objects.select_related('tenant', 'domain')
    serializer_class = EventGuardSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['domain', 'event_guard_enabled', 'event_guard_type']
    search_fields = ['event_guard_name']
