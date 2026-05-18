from rest_framework.routers import DefaultRouter
from .views import RecordingViewSet, CallRecordingViewSet

router = DefaultRouter()
router.register(r'call-recordings', CallRecordingViewSet, basename='call-recording')
router.register(r'', RecordingViewSet, basename='recording')
urlpatterns = router.urls
