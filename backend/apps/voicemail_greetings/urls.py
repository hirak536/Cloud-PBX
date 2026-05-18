from rest_framework.routers import DefaultRouter
from .views import VoicemailGreetingViewSet

router = DefaultRouter()
router.register(r'', VoicemailGreetingViewSet, basename='voicemail-greeting')
urlpatterns = router.urls
