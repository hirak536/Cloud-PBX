from rest_framework.routers import DefaultRouter
from .views import EmailQueueViewSet, EmailDeliveryViewSet

router = DefaultRouter()
# Registered before the catch-all r'' route, which would otherwise swallow it.
router.register(r'deliveries', EmailDeliveryViewSet, basename='email-delivery')
router.register(r'', EmailQueueViewSet, basename='email-queue')
urlpatterns = router.urls
