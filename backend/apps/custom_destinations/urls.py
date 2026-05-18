from rest_framework.routers import DefaultRouter
from .views import CustomDestinationViewSet

router = DefaultRouter()
router.register(r'', CustomDestinationViewSet, basename='custom-destination')

urlpatterns = router.urls
