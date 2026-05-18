from rest_framework.routers import DefaultRouter
from .views import EmailQueueViewSet

router = DefaultRouter()
router.register(r'', EmailQueueViewSet, basename='email-queue')
urlpatterns = router.urls
