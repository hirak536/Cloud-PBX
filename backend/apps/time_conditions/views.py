from rest_framework import viewsets, filters
from django_filters.rest_framework import DjangoFilterBackend
from core.mixins import TenantScopedViewSetMixin
from .models import TimeCondition, TimeConditionRange
from .serializers import TimeConditionSerializer, TimeConditionListSerializer, TimeConditionRangeSerializer

class TimeConditionViewSet(TenantScopedViewSetMixin, viewsets.ModelViewSet):
    queryset = TimeCondition.objects.select_related('tenant', 'domain').prefetch_related('ranges')
    serializer_class = TimeConditionSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['domain', 'dialplan_enabled']
    search_fields = ['dialplan_name', 'dialplan_extension']
    ordering_fields = ['dialplan_name']

    def get_serializer_class(self):
        if self.action == 'list':
            return TimeConditionListSerializer
        return TimeConditionSerializer

class TimeConditionRangeViewSet(TenantScopedViewSetMixin, viewsets.ModelViewSet):
    queryset = TimeConditionRange.objects.select_related('tenant', 'domain')
    serializer_class = TimeConditionRangeSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['dialplan']
