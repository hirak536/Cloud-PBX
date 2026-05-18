from rest_framework.routers import DefaultRouter
from .views import CallBroadcastViewSet, CallBroadcastContactViewSet

router = DefaultRouter()
router.register(r'', CallBroadcastViewSet, basename='call-broadcast')
router.register(r'contacts', CallBroadcastContactViewSet, basename='call-broadcast-contact')
urlpatterns = router.urls
