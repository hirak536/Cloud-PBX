from rest_framework.routers import DefaultRouter
from .views import EventGuardViewSet

router = DefaultRouter()
router.register(r'', EventGuardViewSet, basename='event-guard')
urlpatterns = router.urls
