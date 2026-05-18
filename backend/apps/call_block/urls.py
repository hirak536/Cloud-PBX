from rest_framework.routers import DefaultRouter
from .views import CallBlockViewSet

router = DefaultRouter()
router.register(r'', CallBlockViewSet, basename='call-block')
urlpatterns = router.urls
