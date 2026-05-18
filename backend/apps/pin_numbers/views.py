from rest_framework import viewsets, filters
from django_filters.rest_framework import DjangoFilterBackend
from core.mixins import TenantScopedViewSetMixin
from .models import PinNumber
from .serializers import PinNumberSerializer

class PinNumberViewSet(TenantScopedViewSetMixin, viewsets.ModelViewSet):
    queryset = PinNumber.objects.select_related('tenant', 'domain')
    serializer_class = PinNumberSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['domain', 'pin_number_enabled']
    ordering_fields = ['insert_date']
