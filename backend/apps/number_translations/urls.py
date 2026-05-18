from rest_framework.routers import DefaultRouter
from .views import NumberTranslationViewSet, NumberTranslationDetailViewSet

router = DefaultRouter()
router.register(r'', NumberTranslationViewSet, basename='number-translation')
router.register(r'details', NumberTranslationDetailViewSet, basename='number-translation-detail')
urlpatterns = router.urls
