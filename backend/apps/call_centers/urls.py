from rest_framework.routers import DefaultRouter
from .views import CallCenterViewSet, CallCenterAgentViewSet, CallCenterTierViewSet

router = DefaultRouter()
router.register(r'agents', CallCenterAgentViewSet, basename='call-center-agent')
router.register(r'tiers', CallCenterTierViewSet, basename='call-center-tier')
router.register(r'', CallCenterViewSet, basename='call-center')
urlpatterns = router.urls
