from rest_framework.routers import DefaultRouter
from .views import IvrMenuViewSet, IvrMenuOptionViewSet

router = DefaultRouter()
router.register(r'', IvrMenuViewSet, basename='ivr-menu')
router.register(r'options', IvrMenuOptionViewSet, basename='ivr-menu-option')
urlpatterns = router.urls
