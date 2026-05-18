from rest_framework import viewsets, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from core.permissions import IsSuperAdmin
from .models import OutboundRoute
from .serializers import OutboundRouteSerializer, OutboundRouteListSerializer


class OutboundRouteViewSet(viewsets.ModelViewSet):
    """Global outbound routes — readable by all authenticated users, editable by superadmins only."""
    queryset = OutboundRoute.objects.select_related('gateway', 'gateway_2', 'gateway_3')
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['outbound_route_enabled']
    search_fields = ['outbound_route_name', 'dialplan_pattern', 'outbound_route_description']
    ordering_fields = ['outbound_route_order', 'outbound_route_name']
    ordering = ['outbound_route_order', 'outbound_route_name']

    def get_permissions(self):
        if self.action in ('list', 'retrieve'):
            return [permissions.IsAuthenticated()]
        return [permissions.IsAuthenticated(), IsSuperAdmin()]

    def get_serializer_class(self):
        return OutboundRouteListSerializer if self.action == 'list' else OutboundRouteSerializer

    @action(detail=False, methods=['post'])
    def reload(self, request):
        """Queue a FreeSWITCH XML reload after route changes."""
        try:
            from esl.tasks import reload_xml
            reload_xml.delay()
        except Exception:
            pass
        return Response({'status': 'queued'})
