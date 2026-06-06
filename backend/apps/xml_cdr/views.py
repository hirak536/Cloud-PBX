import csv
from django.http import HttpResponse
from django.db.models import Count, Sum, Avg, Q
from rest_framework import viewsets, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from core.mixins import TenantScopedViewSetMixin
from .models import XmlCdr
from .serializers import XmlCdrSerializer


class XmlCdrViewSet(TenantScopedViewSetMixin, viewsets.ReadOnlyModelViewSet):
    queryset = XmlCdr.objects.select_related('tenant', 'domain')
    serializer_class = XmlCdrSerializer
    permission_classes = [permissions.IsAuthenticated]
    cache_timeout = 0  # Disable caching — CDRs update frequently
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['direction', 'hangup_cause', 'missed_call', 'leg']
    search_fields = ['caller_id_number', 'caller_id_name', 'destination_number']
    ordering_fields = ['start_stamp', 'duration', 'billsec', 'insert_date']
    ordering = ['-start_stamp']

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        # Extensions whose no-answer routing lands on voicemail — a missed call to
        # one of these is reported as voicemail across every CDR API. The admin list
        # spans tenants, so the lookup is global; identifiers are mostly the
        # tenant-suffixed sip_username form ("906-IHDT"), which is unique per tenant.
        from apps.common.vm_routing import vm_route_idents  # noqa: PLC0415
        ctx['vm_route_idents'] = vm_route_idents()
        return ctx

    def get_queryset(self):
        qs = super().get_queryset()
        # Restrict to the A-leg so each call appears once. Without this the list and
        # summary double-count (every call has both an A-leg and B-leg row), which is
        # what makes the admin CDR view disagree with the client_api view.
        qs = qs.filter(leg='a')
        p = self.request.query_params
        # Accept both naming conventions (frontend sends __gte/__lte; legacy uses start_date/end_date)
        start = p.get('start_stamp__gte') or p.get('start_date')
        end = p.get('start_stamp__lte') or p.get('end_date')
        if start:
            qs = qs.filter(start_stamp__gte=start)
        if end:
            qs = qs.filter(start_stamp__lte=end)
        return qs

    @action(detail=False, methods=['get'])
    def summary(self, request):
        qs = self.get_queryset()
        total = qs.count()
        answered = qs.filter(billsec__gt=0).count()
        data = qs.aggregate(
            total_duration=Sum('duration'),
            total_billsec=Sum('billsec'),
            avg_duration=Avg('duration'),
        )
        return Response({
            'total_calls': total,
            'answered_calls': answered,
            'missed_calls': total - answered,
            'answer_rate': round(answered / total * 100, 1) if total else 0,
            'total_duration': data['total_duration'] or 0,
            'total_billsec': data['total_billsec'] or 0,
            'avg_duration': round(data['avg_duration'] or 0, 1),
        })

    @action(detail=False, methods=['get'])
    def export(self, request):
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="cdr.csv"'
        w = csv.writer(response)
        w.writerow(['Start Time','Caller ID','Caller Name','Destination','Duration','Billsec',
                    'Hangup Cause','Direction','Context'])
        for cdr in self.get_queryset()[:10000]:
            w.writerow([cdr.start_stamp, cdr.caller_id_number, cdr.caller_id_name,
                        cdr.destination_number, cdr.duration, cdr.billsec,
                        cdr.hangup_cause, cdr.direction, cdr.context])
        return response
