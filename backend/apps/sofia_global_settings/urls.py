from rest_framework.routers import DefaultRouter
from .views import SofiaGlobalSettingViewSet

router = DefaultRouter()
router.register(r'', SofiaGlobalSettingViewSet, basename='sofia-global-setting')
urlpatterns = router.urls
