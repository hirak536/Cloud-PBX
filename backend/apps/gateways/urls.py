from rest_framework.routers import DefaultRouter
from .views import GatewayViewSet

router = DefaultRouter()
router.register(r'', GatewayViewSet, basename='gateway')
urlpatterns = router.urls
