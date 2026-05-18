from rest_framework.routers import DefaultRouter
from .views import FeatureCodeViewSet

router = DefaultRouter()
router.register(r'', FeatureCodeViewSet, basename='feature-code')
urlpatterns = router.urls
