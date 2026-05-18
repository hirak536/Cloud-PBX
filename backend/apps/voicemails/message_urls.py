from django.urls import path
from rest_framework.routers import DefaultRouter
from .views import VoicemailMessageViewSet, VoicemailIngestView

router = DefaultRouter()
router.register(r'', VoicemailMessageViewSet, basename='voicemail-message')

urlpatterns = [
    path('ingest/', VoicemailIngestView.as_view(), name='voicemail-ingest'),
] + router.urls
