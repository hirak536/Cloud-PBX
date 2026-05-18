from rest_framework.routers import DefaultRouter
from .views import DialplanViewSet, DialplanDetailViewSet

router = DefaultRouter()
router.register(r'details', DialplanDetailViewSet, basename='dialplan-detail')
router.register(r'', DialplanViewSet, basename='dialplan')
urlpatterns = router.urls
