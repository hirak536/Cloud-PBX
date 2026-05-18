from rest_framework import viewsets, filters
from django_filters.rest_framework import DjangoFilterBackend
from core.mixins import TenantScopedViewSetMixin
from .models import MusicOnHold
from .serializers import MusicOnHoldSerializer

class MusicOnHoldViewSet(TenantScopedViewSetMixin, viewsets.ModelViewSet):
    queryset = MusicOnHold.objects.select_related('tenant', 'domain')
    serializer_class = MusicOnHoldSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['domain']
    search_fields = ['music_on_hold_name']
    ordering_fields = ['music_on_hold_name']
