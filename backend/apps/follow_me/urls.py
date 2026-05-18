from rest_framework.routers import DefaultRouter
from .views import FollowMeViewSet, FollowMeDestinationViewSet

router = DefaultRouter()
router.register(r'', FollowMeViewSet, basename='follow-me')
router.register(r'destinations', FollowMeDestinationViewSet, basename='follow-me-destination')
urlpatterns = router.urls
