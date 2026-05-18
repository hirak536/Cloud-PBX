from rest_framework.routers import DefaultRouter
from .views import VariableViewSet

router = DefaultRouter()
router.register(r'', VariableViewSet, basename='variable')
urlpatterns = router.urls
