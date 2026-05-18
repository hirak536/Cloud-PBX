from django.urls import path
from . import views

urlpatterns = [
    path('fail2ban/', views.Fail2banStatusView.as_view(), name='fail2ban-status'),
    path('fail2ban/ban/', views.Fail2banBanView.as_view(), name='fail2ban-ban'),
    path('fail2ban/unban/', views.Fail2banUnbanView.as_view(), name='fail2ban-unban'),
    path('fail2ban/whitelist/', views.Fail2banWhitelistView.as_view(), name='fail2ban-whitelist'),
    path('ufw/', views.UfwStatusView.as_view(), name='ufw-status'),
    path('iptables/', views.IptablesView.as_view(), name='iptables'),
]
