from rest_framework.routers import DefaultRouter
from .views import CallFlowViewSet, CallFlowOptionViewSet

router = DefaultRouter()
router.register(r'', CallFlowViewSet, basename='call-flow')
router.register(r'options', CallFlowOptionViewSet, basename='call-flow-option')
urlpatterns = router.urls
