from rest_framework import viewsets, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from core.mixins import TenantScopedViewSetMixin
from .models import Dialplan, DialplanDetail
from .serializers import DialplanSerializer, DialplanListSerializer, DialplanDetailSerializer


class DialplanViewSet(TenantScopedViewSetMixin, viewsets.ModelViewSet):
    queryset = Dialplan.objects.select_related('tenant', 'domain').prefetch_related('details')
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['dialplan_enabled', 'dialplan_context', 'dialplan_global', 'dialplan_destination']
    search_fields = ['dialplan_name', 'dialplan_number', 'dialplan_description']
    ordering_fields = ['dialplan_order', 'dialplan_name']

    def get_serializer_class(self):
        return DialplanListSerializer if self.action == 'list' else DialplanSerializer

    @action(detail=False, methods=['post'])
    def reload(self, request):
        from esl.tasks import reload_xml
        reload_xml.delay()
        return Response({'status': 'queued', 'message': 'XML reload queued'})

    @action(detail=False, methods=['get'])
    def inbound(self, request):
        qs = self.get_queryset().filter(dialplan_destination=True)
        serializer = DialplanListSerializer(qs, many=True)
        return Response(serializer.data)


class DialplanDetailViewSet(TenantScopedViewSetMixin, viewsets.ModelViewSet):
    queryset = DialplanDetail.objects.select_related('tenant', 'domain', 'dialplan')
    serializer_class = DialplanDetailSerializer
    permission_classes = [permissions.IsAuthenticated]
