from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import FaxViewSet, FaxFileViewSet, FaxReceiveWebhookView, FaxQuickSendView

# Separate routers so 'files/' isn't swallowed by the fax UUID router
fax_router = DefaultRouter()
fax_router.register(r'', FaxViewSet, basename='fax')

files_router = DefaultRouter()
files_router.register(r'', FaxFileViewSet, basename='fax-file')

urlpatterns = [
    # Fixed paths must come before router catch-all
    path('received/', FaxReceiveWebhookView.as_view(), name='fax-received-webhook'),
    path('quick-send/', FaxQuickSendView.as_view(), name='fax-quick-send'),
    path('files/', include(files_router.urls)),
] + fax_router.urls
