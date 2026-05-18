from rest_framework.routers import DefaultRouter
from .views import FifoViewSet

router = DefaultRouter()
router.register(r'', FifoViewSet, basename='fifo')
urlpatterns = router.urls
