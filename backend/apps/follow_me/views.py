from rest_framework import viewsets, filters
from django_filters.rest_framework import DjangoFilterBackend
from core.mixins import TenantScopedViewSetMixin
from .models import FollowMe, FollowMeDestination
from .serializers import FollowMeSerializer, FollowMeDestinationSerializer

class FollowMeViewSet(TenantScopedViewSetMixin, viewsets.ModelViewSet):
    queryset = FollowMe.objects.select_related('tenant', 'domain').prefetch_related('destinations')
    serializer_class = FollowMeSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['domain']
    search_fields = ['follow_me_name']

class FollowMeDestinationViewSet(TenantScopedViewSetMixin, viewsets.ModelViewSet):
    queryset = FollowMeDestination.objects.select_related('tenant', 'domain')
    serializer_class = FollowMeDestinationSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['follow_me']
