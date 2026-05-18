from rest_framework.routers import DefaultRouter
from .views import ExtensionViewSet, ExtensionUserViewSet

router = DefaultRouter()
router.register(r'users', ExtensionUserViewSet, basename='extension-user')
router.register(r'', ExtensionViewSet, basename='extension')
urlpatterns = router.urls
