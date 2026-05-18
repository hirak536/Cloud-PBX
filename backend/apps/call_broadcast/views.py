from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from core.mixins import TenantScopedViewSetMixin
from .models import CallBroadcast, CallBroadcastContact
from .serializers import CallBroadcastSerializer, CallBroadcastContactSerializer
from esl.tasks import originate_call

class CallBroadcastViewSet(TenantScopedViewSetMixin, viewsets.ModelViewSet):
    queryset = CallBroadcast.objects.select_related('tenant', 'domain').prefetch_related('contacts')
    serializer_class = CallBroadcastSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['domain', 'call_broadcast_enabled']
    search_fields = ['call_broadcast_name']

    @action(detail=True, methods=['post'])
    def start(self, request, pk=None):
        broadcast = self.get_object()
        for contact in broadcast.contacts.filter(call_broadcast_contact_status='pending'):
            originate_call.delay(
                src=broadcast.call_broadcast_caller_id_number,
                dst=contact.call_broadcast_contact_number,
                recording=broadcast.call_broadcast_recording
            )
        return Response({'status': 'broadcast started', 'contacts': broadcast.contacts.count()})

class CallBroadcastContactViewSet(TenantScopedViewSetMixin, viewsets.ModelViewSet):
    queryset = CallBroadcastContact.objects.select_related('tenant', 'domain')
    serializer_class = CallBroadcastContactSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['call_broadcast', 'call_broadcast_contact_status']
