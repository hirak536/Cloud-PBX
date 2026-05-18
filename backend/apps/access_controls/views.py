from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from core.mixins import TenantScopedViewSetMixin
from .models import AccessControl, AccessControlNode
from .serializers import AccessControlSerializer, AccessControlListSerializer, AccessControlNodeSerializer
from esl.tasks import reload_xml

class AccessControlViewSet(TenantScopedViewSetMixin, viewsets.ModelViewSet):
    queryset = AccessControl.objects.select_related('tenant', 'domain').prefetch_related('nodes')
    serializer_class = AccessControlSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['domain']
    search_fields = ['access_control_name']

    def get_serializer_class(self):
        if self.action == 'list':
            return AccessControlListSerializer
        return AccessControlSerializer

    @action(detail=False, methods=['post'])
    def reload(self, request):
        reload_xml.delay()
        return Response({'status': 'ACL reload queued'})

class AccessControlNodeViewSet(TenantScopedViewSetMixin, viewsets.ModelViewSet):
    queryset = AccessControlNode.objects.select_related('tenant', 'domain')
    serializer_class = AccessControlNodeSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['access_control']
