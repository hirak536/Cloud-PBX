from rest_framework.routers import DefaultRouter
from .views import ConferenceViewSet, ConferenceProfileViewSet, ConferenceCenterViewSet

router = DefaultRouter()
router.register(r'profiles', ConferenceProfileViewSet, basename='conference-profile')
router.register(r'centers', ConferenceCenterViewSet, basename='conference-center')
router.register(r'', ConferenceViewSet, basename='conference')
urlpatterns = router.urls
