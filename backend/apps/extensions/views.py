import csv
from django.http import HttpResponse
from rest_framework import viewsets, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from core.mixins import TenantScopedViewSetMixin
from .models import Extension, ExtensionUser
from .serializers import ExtensionSerializer, ExtensionListSerializer, ExtensionUserSerializer


class ExtensionViewSet(TenantScopedViewSetMixin, viewsets.ModelViewSet):
    queryset = Extension.objects.select_related('tenant', 'domain', 'outbound_did')
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['enabled', 'voicemail_enabled', 'call_group', 'user_context', 'extension']
    search_fields = ['extension', 'number_alias', 'effective_caller_id_name',
                     'effective_caller_id_number', 'description',
                     'outbound_did__destination_number', 'outbound_did__destination_name']
    ordering_fields = ['extension', 'effective_caller_id_name', 'insert_date']
    ordering = ['extension']

    def get_serializer_class(self):
        return ExtensionListSerializer if self.action == 'list' else ExtensionSerializer

    @action(detail=True, methods=['post'])
    def reload(self, request, pk=None):
        from esl.tasks import reload_xml
        reload_xml.delay()
        return Response({'status': 'queued'})

    @action(detail=False, methods=['get'], url_path='check_number')
    def check_number(self, request):
        """Return whether a number is free across all models (Extension, RingGroup, IvrMenu, CallParkingSlot)."""
        from apps.common.extension_conflict import check_extension_conflict
        number = request.query_params.get('number', '').strip()
        exclude_pk = request.query_params.get('exclude_pk', None)
        if not number:
            return Response({'available': False, 'conflicts': ['No number provided.']})
        from core.models import Tenant
        tenant = None
        tenant_uuid = request.query_params.get('tenant')
        if tenant_uuid:
            tenant = Tenant.objects.filter(tenant_uuid=tenant_uuid).first()
        if not tenant:
            tenant = getattr(request.user, 'tenant', None)
        if not tenant:
            return Response({'available': False, 'conflicts': ['Tenant context could not be determined.']}, status=400)
        conflicts = check_extension_conflict(number, tenant, exclude_model=None, exclude_pk=exclude_pk)
        return Response({'available': len(conflicts) == 0, 'conflicts': conflicts})

    @action(detail=False, methods=['post'], url_path='bulk_delete')
    def bulk_delete(self, request):
        """Delete multiple extensions at once. Payload: {"ids": [uuid, ...]}.

        Scoped through get_queryset() so a tenant can only delete its own rows;
        any id not visible to the caller is reported back as skipped.
        """
        ids = request.data.get('ids') or []
        if not isinstance(ids, list) or not ids:
            return Response({'detail': 'Provide a non-empty "ids" list.'}, status=400)
        qs = self.get_queryset().filter(pk__in=ids)
        found = [str(pk) for pk in qs.values_list('pk', flat=True)]
        deleted_count = qs.count()
        qs.delete()
        skipped = [str(i) for i in ids if str(i) not in set(found)]
        if deleted_count:
            from esl.tasks import reload_xml
            reload_xml.delay()
        return Response({'deleted': found, 'deleted_count': deleted_count, 'skipped': skipped})

    @action(detail=False, methods=['get'])
    def export(self, request):
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="extensions.csv"'
        w = csv.writer(response)
        w.writerow(['Extension','Number Alias','Caller ID Name','Caller ID Number','Voicemail','Enabled'])
        for e in self.get_queryset():
            w.writerow([e.extension, e.number_alias, e.effective_caller_id_name,
                        e.effective_caller_id_number, e.voicemail_enabled, e.enabled])
        return response


class ExtensionUserViewSet(TenantScopedViewSetMixin, viewsets.ModelViewSet):
    queryset = ExtensionUser.objects.select_related('tenant', 'domain', 'extension', 'user')
    serializer_class = ExtensionUserSerializer
    permission_classes = [permissions.IsAuthenticated]
