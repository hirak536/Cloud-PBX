from rest_framework.routers import DefaultRouter
from .views import TimeConditionViewSet, TimeConditionRangeViewSet

router = DefaultRouter()
router.register(r'', TimeConditionViewSet, basename='time-condition')
router.register(r'ranges', TimeConditionRangeViewSet, basename='time-condition-range')
urlpatterns = router.urls
