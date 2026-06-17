from django.urls import path, re_path
from . import views

# Superuser management endpoints (JWT auth)
management_patterns = [
    path('api-keys/', views.APIKeyManagementView.as_view(), name='apikey-list'),
    path('api-keys/<uuid:pk>/', views.APIKeyDetailView.as_view(), name='apikey-detail'),
    path('system-log/', views.SystemLogView.as_view(), name='system-log'),
    path('stats-report/', views.StatsReportView.as_view(), name='stats-report'),
]

# Client API endpoints (ApiKey auth)
client_patterns = [
    path('tenants/', views.ClientTenantListView.as_view(), name='client-tenant-list'),
    path('tenant/', views.ClientTenantView.as_view(), name='client-tenant'),
    path('<uuid:tenant_uuid>/extensions/', views.ClientExtensionView.as_view(), name='client-extensions'),
    path('<uuid:tenant_uuid>/extensions/<uuid:extension_uuid>/', views.ClientExtensionView.as_view(), name='client-extension-detail'),
    path('<uuid:tenant_uuid>/destinations/', views.ClientDestinationView.as_view(), name='client-destinations'),
    path('<uuid:tenant_uuid>/destinations/<uuid:destination_uuid>/', views.ClientDestinationView.as_view(), name='client-destination-detail'),
    path('<uuid:tenant_uuid>/cdr/', views.ClientCDRView.as_view(), name='client-cdr'),
    path('<uuid:tenant_uuid>/cdr/active-extensions/', views.ClientCDRActiveExtensionsView.as_view(), name='client-cdr-active-extensions'),
    path('<uuid:tenant_uuid>/cdr/hourly-stats/', views.ClientCDRHourlyStatsView.as_view(), name='client-cdr-hourly-stats'),
    path('<uuid:tenant_uuid>/cdr/top-extensions/', views.ClientCDRTopExtensionsView.as_view(), name='client-cdr-top-extensions'),
    path('<uuid:tenant_uuid>/cdr/extension-call-summary/', views.ClientExtensionCallSummaryView.as_view(), name='client-extension-call-summary'),
    path('<uuid:tenant_uuid>/cdr/daily-summary/', views.ClientCDRDailySummaryView.as_view(), name='client-cdr-daily-summary'),
    path('<uuid:tenant_uuid>/cdr/summary/', views.ClientCDRView.as_view(), {'xml_cdr_uuid': 'summary'}, name='client-cdr-summary'),
    path('<uuid:tenant_uuid>/summary/', views.ClientCDRView.as_view(), {'xml_cdr_uuid': 'summary'}, name='client-summary'),
    path('<uuid:tenant_uuid>/cdr/<uuid:xml_cdr_uuid>/', views.ClientCDRView.as_view(), name='client-cdr-detail'),
    path('<uuid:tenant_uuid>/fax/', views.ClientFaxView.as_view(), name='client-fax'),
    path('<uuid:tenant_uuid>/fax/files/', views.ClientFaxFileView.as_view(), name='client-fax-files'),
    # Trailing slash optional: external API clients frequently omit it. Without this,
    # APPEND_SLASH issues a 301 redirect, and a 301 on DELETE/POST loses the method/body
    # so the request silently fails. Matching both forms directly avoids the redirect.
    re_path(r'^(?P<tenant_uuid>[0-9a-f-]{36})/fax/files/(?P<fax_file_uuid>[0-9a-f-]{36})/?$',
            views.ClientFaxFileDetailView.as_view(), name='client-fax-file-detail'),
    re_path(r'^(?P<tenant_uuid>[0-9a-f-]{36})/fax/files/(?P<fax_file_uuid>[0-9a-f-]{36})/cancel/?$',
            views.ClientFaxFileCancelView.as_view(), name='client-fax-file-cancel'),
    path('<uuid:tenant_uuid>/fax/files/<uuid:fax_file_uuid>/download/', views.ClientFaxFileDownloadView.as_view(), name='client-fax-file-download'),
    path('<uuid:tenant_uuid>/fax/quick-send/', views.ClientFaxQuickSendView.as_view(), name='client-fax-send'),
    path('<uuid:tenant_uuid>/fax/<uuid:fax_uuid>/', views.ClientFaxView.as_view(), name='client-fax-detail'),
    path('<uuid:tenant_uuid>/call-recordings/', views.ClientCallRecordingView.as_view(), name='client-call-recordings'),
    path('<uuid:tenant_uuid>/call-recordings/<uuid:recording_uuid>/', views.ClientCallRecordingView.as_view(), name='client-call-recording-detail'),
    path('<uuid:tenant_uuid>/call-recordings/<uuid:recording_uuid>/audio/', views.ClientCallRecordingAudioView.as_view(), name='client-call-recording-audio'),
    path('<uuid:tenant_uuid>/voicemail-messages/', views.ClientVoicemailMessageView.as_view(), name='client-voicemail-messages'),
    path('<uuid:tenant_uuid>/voicemail-unread-counts/', views.ClientVoicemailUnreadCountsView.as_view(), name='client-voicemail-unread-counts'),
    path('<uuid:tenant_uuid>/voicemail-messages/<str:message_uuid>/', views.ClientVoicemailMessageView.as_view(), name='client-voicemail-message-detail'),
    path('<uuid:tenant_uuid>/voicemail-messages/<str:message_uuid>/mark-read/', views.ClientVoicemailMessageView.as_view(), name='client-voicemail-mark-read'),
    path('<uuid:tenant_uuid>/voicemail-messages/<str:message_uuid>/audio/', views.ClientVoicemailAudioView.as_view(), name='client-voicemail-audio'),
]

urlpatterns = management_patterns + client_patterns
