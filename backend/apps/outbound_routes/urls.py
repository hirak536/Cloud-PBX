from rest_framework.routers import DefaultRouter
from .views import OutboundRouteViewSet

router = DefaultRouter()
router.register(r'', OutboundRouteViewSet, basename='outbound-routes')
urlpatterns = router.urls
