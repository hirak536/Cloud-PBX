"""URL configuration for the core app.

Mount this file under the project's root URLconf, e.g.::

    path('api/core/', include('core.urls')),

Registered routes
-----------------
Auth (non-router):
  POST  /auth/login/       - obtain JWT access + refresh tokens
  POST  /auth/logout/      - blacklist refresh token
  POST  /auth/refresh/     - rotate / refresh access token (simplejwt)
  GET   /auth/me/          - return current user profile + permissions

Router-generated ViewSet routes:
  /domains/                - DomainViewSet
  /users/                  - UserViewSet
  /groups/                 - GroupViewSet
  /group-permissions/      - GroupPermissionViewSet
  /user-groups/            - UserGroupViewSet
  /user-settings/          - UserSettingViewSet
  /user-logs/              - UserLogViewSet  (read-only)
  /default-settings/       - DefaultSettingViewSet
  /domain-settings/        - DomainSettingViewSet
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView

from . import views

app_name = 'core'

router = DefaultRouter()
router.register(r'tenants', views.TenantViewSet, basename='tenant')
router.register(r'domains', views.DomainViewSet, basename='domain')
router.register(r'users', views.UserViewSet, basename='user')
router.register(r'groups', views.GroupViewSet, basename='group')
router.register(r'group-permissions', views.GroupPermissionViewSet, basename='group-permission')
router.register(r'user-groups', views.UserGroupViewSet, basename='user-group')
router.register(r'user-settings', views.UserSettingViewSet, basename='user-setting')
router.register(r'user-logs', views.UserLogViewSet, basename='user-log')
router.register(r'audit-logs', views.AuditLogViewSet, basename='audit-log')
router.register(r'default-settings', views.DefaultSettingViewSet, basename='default-setting')
router.register(r'domain-settings', views.DomainSettingViewSet, basename='domain-setting')

urlpatterns = [
    # Authentication endpoints
    path('auth/login/', views.LoginView.as_view(), name='login'),
    path('auth/logout/', views.LogoutView.as_view(), name='logout'),
    path('auth/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('auth/me/', views.MeView.as_view(), name='me'),
    path('auth/reset-password/', views.ResetPasswordView.as_view(), name='reset_password'),
    path('auth/forgot-password/', views.ForgotPasswordView.as_view(), name='forgot_password'),
    path('auth/change-password/', views.ChangePasswordView.as_view(), name='change_password'),

    # ViewSet routes
    path('', include(router.urls)),

    # System cache flush (superusers only)
    path('cache/flush/', views.FlushCacheView.as_view(), name='cache_flush'),
]
