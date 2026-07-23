from rest_framework import viewsets, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter
from core.mixins import TenantScopedViewSetMixin
from .models import Conference, ConferenceProfile, ConferenceProfileSetting, ConferenceCenter
from .serializers import ConferenceSerializer, ConferenceProfileSerializer, ConferenceCenterSerializer
from .permissions import ConferencePermission


class ConferenceViewSet(TenantScopedViewSetMixin, viewsets.ModelViewSet):
    queryset = Conference.objects.select_related('tenant', 'domain', 'conference_profile')
    serializer_class = ConferenceSerializer
    permission_classes = [permissions.IsAuthenticated, ConferencePermission]
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ['conference_enabled', 'conference_record']
    search_fields = ['conference_name', 'conference_extension', 'conference_description']

    @action(detail=True, methods=['get'])
    def active(self, request, pk=None):
        conf = self.get_object()
        try:
            from esl.client import get_esl_client
            esl = get_esl_client()
            result = esl.conference_cmd(conf.conference_name, 'list')
            return Response({'conference': conf.conference_name, 'members': result})
        except Exception as e:
            return Response({'error': str(e)}, status=503)

    @action(detail=True, methods=['post'])
    def kick(self, request, pk=None):
        conf = self.get_object()
        member_id = request.data.get('member_id', 'all')
        try:
            from esl.client import get_esl_client
            esl = get_esl_client()
            result = esl.conference_cmd(conf.conference_name, f'kick {member_id}')
            return Response({'result': result})
        except Exception as e:
            return Response({'error': str(e)}, status=503)


class ConferenceProfileViewSet(TenantScopedViewSetMixin, viewsets.ModelViewSet):
    queryset = ConferenceProfile.objects.select_related('tenant', 'domain').prefetch_related('settings')
    serializer_class = ConferenceProfileSerializer
    permission_classes = [permissions.IsAuthenticated]


class ConferenceCenterViewSet(TenantScopedViewSetMixin, viewsets.ModelViewSet):
    queryset = ConferenceCenter.objects.select_related('tenant', 'domain')
    serializer_class = ConferenceCenterSerializer
    permission_classes = [permissions.IsAuthenticated]
