from rest_framework import viewsets, filters
from django_filters.rest_framework import DjangoFilterBackend
from core.mixins import TenantScopedViewSetMixin
from .models import NumberTranslation, NumberTranslationDetail
from .serializers import NumberTranslationSerializer, NumberTranslationDetailSerializer

class NumberTranslationViewSet(TenantScopedViewSetMixin, viewsets.ModelViewSet):
    queryset = NumberTranslation.objects.select_related('tenant', 'domain').prefetch_related('details')
    serializer_class = NumberTranslationSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['domain']
    search_fields = ['number_translation_name']

class NumberTranslationDetailViewSet(TenantScopedViewSetMixin, viewsets.ModelViewSet):
    queryset = NumberTranslationDetail.objects.select_related('tenant', 'domain')
    serializer_class = NumberTranslationDetailSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['number_translation']
