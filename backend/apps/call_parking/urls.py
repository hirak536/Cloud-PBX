from rest_framework.routers import DefaultRouter
from .views import CallParkingSlotViewSet

router = DefaultRouter()
router.register(r'', CallParkingSlotViewSet, basename='call-parking-lot')
urlpatterns = router.urls
