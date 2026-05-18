from rest_framework.routers import DefaultRouter
from .views import ExtensionSettingViewSet

router = DefaultRouter()
router.register(r'', ExtensionSettingViewSet, basename='extension-setting')
urlpatterns = router.urls
