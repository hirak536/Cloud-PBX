from rest_framework.routers import DefaultRouter
from .views import AccessControlViewSet, AccessControlNodeViewSet

router = DefaultRouter()
router.register(r'', AccessControlViewSet, basename='access-control')
router.register(r'nodes', AccessControlNodeViewSet, basename='access-control-node')
urlpatterns = router.urls
