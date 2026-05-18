from rest_framework import viewsets, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import SofiaGlobalSetting
from .serializers import SofiaGlobalSettingSerializer


class SofiaGlobalSettingViewSet(viewsets.ModelViewSet):
    queryset = SofiaGlobalSetting.objects.all()
    serializer_class = SofiaGlobalSettingSerializer
    permission_classes = [permissions.IsAuthenticated]
    search_fields = ['sofia_global_setting_name', 'sofia_global_setting_value']
    filterset_fields = ['sofia_global_setting_enabled']
    ordering_fields = ['sofia_global_setting_name']

    @action(detail=False, methods=['post'])
    def reload(self, request):
        """Reload FreeSWITCH XML configuration to apply changes."""
        from esl.tasks import reload_xml
        reload_xml.delay()
        return Response({'status': 'reloading', 'message': 'XML reload queued'})
