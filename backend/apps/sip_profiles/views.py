from rest_framework import viewsets, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import SipProfile, SipProfileSetting, SipProfileDomain
from .serializers import SipProfileSerializer, SipProfileSettingSerializer, SipProfileDomainSerializer


class SipProfileViewSet(viewsets.ModelViewSet):
    queryset = SipProfile.objects.prefetch_related('settings', 'domains')
    serializer_class = SipProfileSerializer
    permission_classes = [permissions.IsAuthenticated]
    search_fields = ['sip_profile_name', 'sip_profile_description']
    filterset_fields = ['sip_profile_enabled']

    @action(detail=True, methods=['post'])
    def reload(self, request, pk=None):
        profile = self.get_object()
        try:
            from esl.client import get_esl_client
            esl = get_esl_client()
            result = esl.sofia_reload(profile.sip_profile_name)
            return Response({'status': 'reloaded', 'result': result})
        except Exception as e:
            return Response({'error': str(e)}, status=503)

    @action(detail=True, methods=['get'])
    def status(self, request, pk=None):
        profile = self.get_object()
        try:
            from esl.client import get_esl_client
            esl = get_esl_client()
            result = esl.api(f'sofia status profile {profile.sip_profile_name}')
            return Response({'profile': profile.sip_profile_name, 'status': result})
        except Exception as e:
            return Response({'error': str(e)}, status=503)


class SipProfileSettingViewSet(viewsets.ModelViewSet):
    queryset = SipProfileSetting.objects.select_related('sip_profile')
    serializer_class = SipProfileSettingSerializer
    permission_classes = [permissions.IsAuthenticated]


class SipProfileDomainViewSet(viewsets.ModelViewSet):
    queryset = SipProfileDomain.objects.select_related('sip_profile')
    serializer_class = SipProfileDomainSerializer
    permission_classes = [permissions.IsAuthenticated]
