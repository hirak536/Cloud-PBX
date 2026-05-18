from rest_framework.routers import DefaultRouter
from .views import RingGroupViewSet, RingGroupDestinationViewSet

router = DefaultRouter()
router.register(r'destinations', RingGroupDestinationViewSet, basename='ring-group-destination')
router.register(r'', RingGroupViewSet, basename='ring-group')
urlpatterns = router.urls
