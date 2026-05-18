from rest_framework import viewsets, permissions
from rest_framework.filters import SearchFilter
from django_filters.rest_framework import DjangoFilterBackend
from core.mixins import TenantScopedViewSetMixin
from .models import CustomDestination
from .serializers import CustomDestinationSerializer, CustomDestinationListSerializer


class CustomDestinationViewSet(TenantScopedViewSetMixin, viewsets.ModelViewSet):
    queryset = CustomDestination.objects.select_related('tenant', 'domain')
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ['enabled', 'dest_type']
    search_fields = ['name', 'description']

    def get_serializer_class(self):
        if self.action == 'list':
            return CustomDestinationListSerializer
        return CustomDestinationSerializer
