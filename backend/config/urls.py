"""Root URL configuration."""
from pathlib import Path
from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.conf.urls.static import static
from django.http import FileResponse, HttpResponse


def spa_index(request):
    """Serve the React SPA index.html for all non-API routes."""
    index_path = Path(settings.BASE_DIR).parent / 'frontend' / 'dist' / 'index.html'
    if index_path.exists():
        return FileResponse(open(index_path, 'rb'), content_type='text/html')
    return HttpResponse(
        'Frontend not built. Run: cd frontend && npm run build',
        status=503,
        content_type='text/plain',
    )
urlpatterns = [
    # Django admin
    path('admin/', admin.site.urls),

    # API v1
    path('api/v1/', include([
        # Core: auth, domains, users, groups
        path('', include('core.urls')),

        # PBX Apps
        path('extensions/', include('apps.extensions.urls')),
        path('dialplans/', include('apps.dialplans.urls')),
        path('voicemails/', include('apps.voicemails.urls')),
        path('voicemail-messages/', include('apps.voicemails.message_urls')),
        path('gateways/', include('apps.gateways.urls')),
        path('sip-profiles/', include('apps.sip_profiles.urls')),
        path('sofia-global-settings/', include('apps.sofia_global_settings.urls')),
        path('voicemail-greetings/', include('apps.voicemail_greetings.urls')),
        path('extension-settings/', include('apps.extension_settings.urls')),
        path('call-centers/', include('apps.call_centers.urls')),
        path('conferences/', include('apps.conferences.urls')),
        path('devices/', include('apps.devices.urls')),
        path('provision/', include('apps.provision.urls')),
        path('cdr/', include('apps.xml_cdr.urls')),
        path('recordings/', include('apps.recordings.urls')),
        path('ring-groups/', include('apps.ring_groups.urls')),
        path('ivr-menus/', include('apps.ivr_menus.urls')),
        path('call-flows/', include('apps.call_flows.urls')),
        path('time-conditions/', include('apps.time_conditions.urls')),
        path('destinations/', include('apps.destinations.urls')),
        path('feature-codes/', include('apps.feature_codes.urls')),
        path('access-controls/', include('apps.access_controls.urls')),
        path('music-on-hold/', include('apps.music_on_hold.urls')),
        path('fax/', include('apps.fax.urls')),
        path('email-queue/', include('apps.email_queue.urls')),
        path('number-translations/', include('apps.number_translations.urls')),
        path('modules/', include('apps.modules_app.urls')),
        path('pin-numbers/', include('apps.pin_numbers.urls')),
        path('vars/', include('apps.vars.urls')),
        path('follow-me/', include('apps.follow_me.urls')),
        path('call-block/', include('apps.call_block.urls')),
        path('call-broadcast/', include('apps.call_broadcast.urls')),
        path('fifo/', include('apps.fifo.urls')),
        path('emergency/', include('apps.emergency.urls')),
        path('event-guard/', include('apps.event_guard.urls')),
        path('domain-limits/', include('apps.domain_limits.urls')),
        path('working-hours/', include('apps.working_hours.urls')),
        path('outbound-routes/', include('apps.outbound_routes.urls')),
        path('custom-destinations/', include('apps.custom_destinations.urls')),
        path('call-parking/', include('apps.call_parking.urls')),

        # Client API (server-to-server, ApiKey auth) + superuser key management
        path('client/', include('apps.client_api.urls')),

        # FreeSWITCH ESL direct commands
        path('freeswitch/', include('esl.urls')),

        # Firewall / Fail2ban management
        path('firewall/', include('apps.firewall.urls')),
    ])),

    # FreeSWITCH XML cURL handler (called by FreeSWITCH itself)
    path('xml-curl/', include('freeswitch_config.urls')),

]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

# Catch-all: serve React SPA for any unmatched route (HTML5 history routing)
urlpatterns += [
    re_path(r'^(?!api/|admin/|xml-curl/|provision/|static/|media/).*$', spa_index),
]
