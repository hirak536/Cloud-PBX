from rest_framework.routers import DefaultRouter
from .views import MusicOnHoldViewSet

router = DefaultRouter()
router.register(r'', MusicOnHoldViewSet, basename='music-on-hold')
urlpatterns = router.urls
