from rest_framework import viewsets, filters
from django_filters.rest_framework import DjangoFilterBackend
from core.mixins import TenantScopedViewSetMixin
from .models import Variable
from .serializers import VariableSerializer

class VariableViewSet(TenantScopedViewSetMixin, viewsets.ModelViewSet):
    queryset = Variable.objects.select_related('tenant', 'domain')
    serializer_class = VariableSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['domain', 'variable_enabled']
    search_fields = ['variable_name']
    ordering_fields = ['variable_name']
