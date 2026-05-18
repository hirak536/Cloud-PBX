from rest_framework.routers import DefaultRouter
from .views import WorkingHoursViewSet, WorkingHoursDayViewSet, WorkingHoursHolidayViewSet

router = DefaultRouter()
router.register(r'', WorkingHoursViewSet, basename='working-hours')
router.register(r'days', WorkingHoursDayViewSet, basename='working-hours-day')
router.register(r'holidays', WorkingHoursHolidayViewSet, basename='working-hours-holiday')

urlpatterns = router.urls
