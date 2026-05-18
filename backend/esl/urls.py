from django.urls import path
from . import views

urlpatterns = [
    path('status/', views.FSStatusView.as_view(), name='fs-status'),
    path('api/', views.FSApiView.as_view(), name='fs-api'),
    path('calls/', views.FSCallsView.as_view(), name='fs-calls'),
    path('channels/', views.FSChannelsView.as_view(), name='fs-channels'),
    path('registrations/', views.FSRegistrationsView.as_view(), name='fs-registrations'),
    path('deregister/', views.FSDeregisterView.as_view(), name='fs-deregister'),
    path('originate/', views.FSOriginateView.as_view(), name='fs-originate'),
    path('hangup/', views.FSHangupView.as_view(), name='fs-hangup'),
    path('transfer/', views.FSTransferView.as_view(), name='fs-transfer'),
    path('sofia/', views.FSSofiaView.as_view(), name='fs-sofia'),
    path('eavesdrop/', views.FSEavesdropView.as_view(), name='fs-eavesdrop'),
    path('db-stats/', views.FSDbStatsView.as_view(), name='fs-db-stats'),
    path('log/', views.FSLogView.as_view(), name='fs-log'),
    path('server-health/', views.FSServerHealthView.as_view(), name='fs-server-health'),
]
