from rest_framework.routers import DefaultRouter
from .views import DeviceViewSet, DeviceLineViewSet, DeviceSettingViewSet

router = DefaultRouter()
router.register(r'', DeviceViewSet, basename='device')
router.register(r'lines', DeviceLineViewSet, basename='device-line')
router.register(r'device-settings', DeviceSettingViewSet, basename='device-setting')
urlpatterns = router.urls
