from rest_framework.routers import DefaultRouter
from .views import XmlCdrViewSet

router = DefaultRouter()
router.register(r'', XmlCdrViewSet, basename='cdr')
urlpatterns = router.urls
