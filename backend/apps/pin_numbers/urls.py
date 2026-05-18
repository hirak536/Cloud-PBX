from rest_framework.routers import DefaultRouter
from .views import PinNumberViewSet

router = DefaultRouter()
router.register(r'', PinNumberViewSet, basename='pin-number')
urlpatterns = router.urls
