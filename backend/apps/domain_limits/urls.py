from rest_framework.routers import DefaultRouter
from .views import DomainLimitViewSet

router = DefaultRouter()
router.register(r'', DomainLimitViewSet, basename='domain-limit')
urlpatterns = router.urls
