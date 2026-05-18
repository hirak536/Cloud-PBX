from rest_framework import viewsets, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from core.mixins import TenantScopedViewSetMixin
from .models import Device, DeviceLine, DeviceSetting
from .serializers import DeviceSerializer, DeviceListSerializer, DeviceLineSerializer, DeviceSettingSerializer

class DeviceViewSet(TenantScopedViewSetMixin, viewsets.ModelViewSet):
    queryset = Device.objects.select_related('tenant', 'domain').prefetch_related('lines', 'settings')
    serializer_class = DeviceSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['domain', 'device_vendor', 'device_model', 'device_enabled']
    search_fields = ['device_mac_address', 'device_label', 'device_vendor']
    ordering_fields = ['device_mac_address', 'device_vendor', 'device_model']

    def get_serializer_class(self):
        if self.action == 'list':
            return DeviceListSerializer
        return DeviceSerializer

class DeviceLineViewSet(TenantScopedViewSetMixin, viewsets.ModelViewSet):
    queryset = DeviceLine.objects.select_related('tenant', 'domain')
    serializer_class = DeviceLineSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['device']

class DeviceSettingViewSet(TenantScopedViewSetMixin, viewsets.ModelViewSet):
    queryset = DeviceSetting.objects.select_related('tenant', 'domain')
    serializer_class = DeviceSettingSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['device']
