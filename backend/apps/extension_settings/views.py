from rest_framework import viewsets, filters
from django_filters.rest_framework import DjangoFilterBackend
from core.mixins import TenantScopedViewSetMixin
from .models import ExtensionSetting
from .serializers import ExtensionSettingSerializer

class ExtensionSettingViewSet(TenantScopedViewSetMixin, viewsets.ModelViewSet):
    queryset = ExtensionSetting.objects.select_related('tenant', 'domain')
    serializer_class = ExtensionSettingSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['domain', 'extension_uuid', 'extension_setting_enabled']
    search_fields = ['extension_setting_name', 'extension_setting_category']
