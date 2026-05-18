from rest_framework import viewsets, filters
from django_filters.rest_framework import DjangoFilterBackend
from core.mixins import TenantScopedViewSetMixin
from .models import FeatureCode
from .serializers import FeatureCodeSerializer

class FeatureCodeViewSet(TenantScopedViewSetMixin, viewsets.ModelViewSet):
    queryset = FeatureCode.objects.select_related('tenant', 'domain')
    serializer_class = FeatureCodeSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['domain']
    search_fields = ['feature_code_name']
    ordering_fields = ['feature_code_name']
