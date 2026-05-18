from rest_framework.routers import DefaultRouter
from .views import SipProfileViewSet, SipProfileSettingViewSet, SipProfileDomainViewSet

router = DefaultRouter()
router.register(r'settings', SipProfileSettingViewSet, basename='sip-profile-setting')
router.register(r'profile-domains', SipProfileDomainViewSet, basename='sip-profile-domain')
router.register(r'', SipProfileViewSet, basename='sip-profile')
urlpatterns = router.urls
