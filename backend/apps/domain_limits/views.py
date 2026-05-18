from rest_framework import viewsets, filters
from django_filters.rest_framework import DjangoFilterBackend
from core.mixins import TenantScopedViewSetMixin
from .models import DomainLimit
from .serializers import DomainLimitSerializer

class DomainLimitViewSet(TenantScopedViewSetMixin, viewsets.ModelViewSet):
    queryset = DomainLimit.objects.select_related('tenant', 'domain')
    serializer_class = DomainLimitSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['domain']
    search_fields = ['domain_limit_name']
