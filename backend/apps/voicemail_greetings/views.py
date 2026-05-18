from rest_framework import viewsets, filters
from django_filters.rest_framework import DjangoFilterBackend
from core.mixins import TenantScopedViewSetMixin
from .models import VoicemailGreeting
from .serializers import VoicemailGreetingSerializer

class VoicemailGreetingViewSet(TenantScopedViewSetMixin, viewsets.ModelViewSet):
    queryset = VoicemailGreeting.objects.select_related('tenant', 'domain')
    serializer_class = VoicemailGreetingSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['domain', 'voicemail_id']
    search_fields = ['voicemail_id', 'greeting_name']
