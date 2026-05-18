from rest_framework import viewsets, filters
from django_filters.rest_framework import DjangoFilterBackend
from core.mixins import TenantScopedViewSetMixin
from .models import WorkingHours, WorkingHoursDay, WorkingHoursHoliday
from .serializers import (
    WorkingHoursSerializer,
    WorkingHoursListSerializer,
    WorkingHoursDaySerializer,
    WorkingHoursHolidaySerializer,
)


class WorkingHoursViewSet(TenantScopedViewSetMixin, viewsets.ModelViewSet):
    queryset = WorkingHours.objects.select_related('tenant', 'domain').prefetch_related('days', 'holidays')
    serializer_class = WorkingHoursSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['domain', 'working_hours_enabled']
    search_fields = ['working_hours_name', 'dialplan_extension']
    ordering_fields = ['working_hours_name']

    def get_serializer_class(self):
        if self.action == 'list':
            return WorkingHoursListSerializer
        return WorkingHoursSerializer


class WorkingHoursDayViewSet(TenantScopedViewSetMixin, viewsets.ModelViewSet):
    queryset = WorkingHoursDay.objects.select_related('working_hours', 'tenant')
    serializer_class = WorkingHoursDaySerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['working_hours']


class WorkingHoursHolidayViewSet(TenantScopedViewSetMixin, viewsets.ModelViewSet):
    queryset = WorkingHoursHoliday.objects.select_related('working_hours', 'tenant')
    serializer_class = WorkingHoursHolidaySerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['working_hours']
