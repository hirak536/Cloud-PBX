from rest_framework.routers import DefaultRouter
from .views import VoicemailViewSet, VoicemailMessageViewSet

router = DefaultRouter()
router.register(r'', VoicemailViewSet, basename='voicemail')

urlpatterns = router.urls
