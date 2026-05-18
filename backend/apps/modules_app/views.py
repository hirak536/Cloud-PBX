from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from .models import Module
from .serializers import ModuleSerializer
from esl.client import get_esl_client

class ModuleViewSet(viewsets.ModelViewSet):
    queryset = Module.objects.all()
    serializer_class = ModuleSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['module_category', 'module_enabled']
    search_fields = ['module_name', 'module_label']
    ordering_fields = ['module_category', 'module_sequence']

    @action(detail=True, methods=['post'])
    def load(self, request, pk=None):
        module = self.get_object()
        try:
            esl = get_esl_client()
            result = esl.module_load(module.module_name)
            module.module_enabled = True
            module.save(update_fields=['module_enabled'])
            return Response({'status': 'loaded', 'result': result})
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

    @action(detail=True, methods=['post'])
    def unload(self, request, pk=None):
        module = self.get_object()
        try:
            esl = get_esl_client()
            result = esl.module_unload(module.module_name)
            module.module_enabled = False
            module.save(update_fields=['module_enabled'])
            return Response({'status': 'unloaded', 'result': result})
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

    @action(detail=True, methods=['post'])
    def reload(self, request, pk=None):
        module = self.get_object()
        try:
            esl = get_esl_client()
            result = esl.module_reload(module.module_name)
            return Response({'status': 'reloaded', 'result': result})
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
