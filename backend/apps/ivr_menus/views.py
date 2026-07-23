from rest_framework import viewsets, filters, permissions
from django_filters.rest_framework import DjangoFilterBackend
from core.mixins import TenantScopedViewSetMixin
from .models import IvrMenu, IvrMenuOption
from .serializers import IvrMenuSerializer, IvrMenuListSerializer, IvrMenuOptionSerializer
from .permissions import IvrMenuPermission, IvrMenuOptionPermission

class IvrMenuViewSet(TenantScopedViewSetMixin, viewsets.ModelViewSet):
    queryset = IvrMenu.objects.select_related('tenant', 'domain').prefetch_related('options')
    serializer_class = IvrMenuSerializer
    permission_classes = [permissions.IsAuthenticated, IvrMenuPermission]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['domain', 'ivr_menu_enabled']
    search_fields = ['ivr_menu_name', 'ivr_menu_extension']
    ordering_fields = ['ivr_menu_name', 'ivr_menu_extension']

    def get_serializer_class(self):
        if self.action == 'list':
            return IvrMenuListSerializer
        return IvrMenuSerializer

class IvrMenuOptionViewSet(TenantScopedViewSetMixin, viewsets.ModelViewSet):
    queryset = IvrMenuOption.objects.select_related('tenant', 'domain')
    serializer_class = IvrMenuOptionSerializer
    permission_classes = [permissions.IsAuthenticated, IvrMenuOptionPermission]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['ivr_menu']
