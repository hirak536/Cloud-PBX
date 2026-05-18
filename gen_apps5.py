#!/usr/bin/env python3
"""
gen_apps5.py - voicemail_greetings, extension_settings, provision stub
"""
import os, textwrap

BASE = os.path.join(os.path.dirname(__file__), 'backend', 'apps')

def write(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(textwrap.dedent(content).lstrip('\n'))
    print(f'  WROTE {os.path.basename(path)}')

def make_app(name):
    d = os.path.join(BASE, name)
    os.makedirs(d, exist_ok=True)
    open(os.path.join(d, '__init__.py'), 'a').close()
    mig = os.path.join(d, 'migrations')
    os.makedirs(mig, exist_ok=True)
    open(os.path.join(mig, '__init__.py'), 'a').close()

# ─────────────────────────────────────────────────── voicemail_greetings ──
print('voicemail_greetings...')
make_app('voicemail_greetings')
d = os.path.join(BASE, 'voicemail_greetings')

write(os.path.join(d, 'models.py'), """
    import uuid
    from django.db import models
    from core.models import Domain

    class VoicemailGreeting(models.Model):
        voicemail_greeting_uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
        domain = models.ForeignKey(Domain, on_delete=models.CASCADE, null=True, blank=True, db_column='domain_uuid')
        voicemail_id = models.CharField(max_length=255)
        greeting_id = models.IntegerField(default=0)
        greeting_name = models.CharField(max_length=255, blank=True)
        greeting_filename = models.CharField(max_length=512)
        greeting_description = models.TextField(blank=True)
        insert_date = models.DateTimeField(auto_now_add=True)
        insert_user = models.UUIDField(null=True, blank=True)

        class Meta:
            db_table = 'v_voicemail_greetings'

        def __str__(self):
            return f'{self.voicemail_id} - {self.greeting_name}'
""")

write(os.path.join(d, 'serializers.py'), """
    from rest_framework import serializers
    from .models import VoicemailGreeting

    class VoicemailGreetingSerializer(serializers.ModelSerializer):
        class Meta:
            model = VoicemailGreeting
            fields = '__all__'
            read_only_fields = ['voicemail_greeting_uuid', 'insert_date', 'insert_user']
""")

write(os.path.join(d, 'views.py'), """
    from rest_framework import viewsets, filters
    from django_filters.rest_framework import DjangoFilterBackend
    from .models import VoicemailGreeting
    from .serializers import VoicemailGreetingSerializer

    class VoicemailGreetingViewSet(viewsets.ModelViewSet):
        queryset = VoicemailGreeting.objects.all()
        serializer_class = VoicemailGreetingSerializer
        filter_backends = [DjangoFilterBackend, filters.SearchFilter]
        filterset_fields = ['domain', 'voicemail_id']
        search_fields = ['voicemail_id', 'greeting_name']

        def get_queryset(self):
            qs = super().get_queryset()
            domain = self.request.query_params.get('domain_uuid')
            if domain:
                qs = qs.filter(domain__domain_uuid=domain)
            return qs
""")

write(os.path.join(d, 'urls.py'), """
    from rest_framework.routers import DefaultRouter
    from .views import VoicemailGreetingViewSet

    router = DefaultRouter()
    router.register(r'', VoicemailGreetingViewSet, basename='voicemail-greeting')
    urlpatterns = router.urls
""")

write(os.path.join(d, 'admin.py'), """
    from django.contrib import admin
    from .models import VoicemailGreeting

    @admin.register(VoicemailGreeting)
    class VoicemailGreetingAdmin(admin.ModelAdmin):
        list_display = ['voicemail_id', 'greeting_name', 'greeting_filename', 'insert_date']
        list_filter = ['domain']
        search_fields = ['voicemail_id', 'greeting_name']
""")

# ─────────────────────────────────────────────────── extension_settings ──
print('extension_settings...')
make_app('extension_settings')
d = os.path.join(BASE, 'extension_settings')

write(os.path.join(d, 'models.py'), """
    import uuid
    from django.db import models
    from core.models import Domain

    class ExtensionSetting(models.Model):
        extension_setting_uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
        domain = models.ForeignKey(Domain, on_delete=models.CASCADE, null=True, blank=True, db_column='domain_uuid')
        extension_uuid = models.UUIDField()
        extension_setting_category = models.CharField(max_length=255, blank=True)
        extension_setting_subcategory = models.CharField(max_length=255, blank=True)
        extension_setting_name = models.CharField(max_length=255)
        extension_setting_value = models.TextField(blank=True)
        extension_setting_order = models.IntegerField(default=0)
        extension_setting_enabled = models.BooleanField(default=True)
        extension_setting_description = models.TextField(blank=True)
        insert_date = models.DateTimeField(auto_now_add=True)
        insert_user = models.UUIDField(null=True, blank=True)
        update_date = models.DateTimeField(auto_now=True)
        update_user = models.UUIDField(null=True, blank=True)

        class Meta:
            db_table = 'v_extension_settings'
            ordering = ['extension_setting_order']

        def __str__(self):
            return f'{self.extension_setting_name}={self.extension_setting_value}'
""")

write(os.path.join(d, 'serializers.py'), """
    from rest_framework import serializers
    from .models import ExtensionSetting

    class ExtensionSettingSerializer(serializers.ModelSerializer):
        class Meta:
            model = ExtensionSetting
            fields = '__all__'
            read_only_fields = ['extension_setting_uuid', 'insert_date', 'insert_user', 'update_date', 'update_user']
""")

write(os.path.join(d, 'views.py'), """
    from rest_framework import viewsets, filters
    from django_filters.rest_framework import DjangoFilterBackend
    from .models import ExtensionSetting
    from .serializers import ExtensionSettingSerializer

    class ExtensionSettingViewSet(viewsets.ModelViewSet):
        queryset = ExtensionSetting.objects.all()
        serializer_class = ExtensionSettingSerializer
        filter_backends = [DjangoFilterBackend, filters.SearchFilter]
        filterset_fields = ['domain', 'extension_uuid', 'extension_setting_enabled']
        search_fields = ['extension_setting_name', 'extension_setting_category']

        def get_queryset(self):
            qs = super().get_queryset()
            domain = self.request.query_params.get('domain_uuid')
            if domain:
                qs = qs.filter(domain__domain_uuid=domain)
            return qs
""")

write(os.path.join(d, 'urls.py'), """
    from rest_framework.routers import DefaultRouter
    from .views import ExtensionSettingViewSet

    router = DefaultRouter()
    router.register(r'', ExtensionSettingViewSet, basename='extension-setting')
    urlpatterns = router.urls
""")

write(os.path.join(d, 'admin.py'), """
    from django.contrib import admin
    from .models import ExtensionSetting

    @admin.register(ExtensionSetting)
    class ExtensionSettingAdmin(admin.ModelAdmin):
        list_display = ['extension_uuid', 'extension_setting_name', 'extension_setting_value', 'extension_setting_enabled']
        list_filter = ['extension_setting_enabled', 'extension_setting_category']
        search_fields = ['extension_setting_name']
""")

# ───────────────────────────────────────────────────────────── provision ──
print('provision...')
make_app('provision')
d = os.path.join(BASE, 'provision')

write(os.path.join(d, 'views.py'), """
    import re
    from django.http import HttpResponse, Http404
    from django.views import View
    from apps.devices.models import Device, DeviceLine

    VENDOR_TEMPLATES = {
        'yealink': 'provision/yealink.cfg',
        'grandstream': 'provision/grandstream.cfg',
        'polycom': 'provision/polycom.cfg',
        'cisco': 'provision/cisco.cfg',
        'snom': 'provision/snom.cfg',
    }

    class ProvisionView(View):
        \"\"\"
        Serves device-specific provisioning config files.
        FreeSWITCH phones call this at boot: GET /provision/<mac>/
        \"\"\"
        def get(self, request, mac, *args, **kwargs):
            mac_clean = re.sub(r'[^0-9a-fA-F]', '', mac).lower()
            try:
                device = Device.objects.select_related('domain').prefetch_related('lines').get(
                    device_mac_address__iexact=mac_clean, device_enabled=True
                )
            except Device.DoesNotExist:
                raise Http404(f'Device {mac_clean} not found or not enabled')

            vendor = (device.device_vendor or '').lower()
            config = self._generate_config(device, vendor)
            content_type = 'text/plain'
            if 'xml' in vendor or vendor == 'polycom':
                content_type = 'application/xml'
            return HttpResponse(config, content_type=content_type)

        def _generate_config(self, device, vendor):
            lines = list(device.lines.filter(device_line_enabled=True))
            if vendor == 'yealink':
                return self._yealink_config(device, lines)
            elif vendor == 'grandstream':
                return self._grandstream_config(device, lines)
            elif vendor == 'polycom':
                return self._polycom_config(device, lines)
            else:
                return self._generic_config(device, lines)

        def _yealink_config(self, device, lines):
            cfg = ['#!version:1.0.0.1']
            cfg.append(f'local_time.ntp_server1 = pool.ntp.org')
            cfg.append(f'sip.reg_on = 1')
            for i, line in enumerate(lines, 1):
                cfg.append(f'account.{i}.enable = 1')
                cfg.append(f'account.{i}.label = {line.device_line_label or line.device_line_username}')
                cfg.append(f'account.{i}.display_name = {line.device_line_display_name}')
                cfg.append(f'account.{i}.auth_name = {line.device_line_auth_id or line.device_line_username}')
                cfg.append(f'account.{i}.user_name = {line.device_line_username}')
                cfg.append(f'account.{i}.password = {line.device_line_password}')
                cfg.append(f'account.{i}.sip_server_host = {line.device_line_server_address}')
            return '\\n'.join(cfg)

        def _grandstream_config(self, device, lines):
            cfg = ['<?xml version="1.0" encoding="UTF-8"?>', '<gs_provision version="1">',
                   '  <config version="1">']
            for i, line in enumerate(lines, 1):
                cfg.append(f'    <P{35+i}>{line.device_line_server_address}</P{35+i}>')
                cfg.append(f'    <P{400+i}>{line.device_line_username}</P{400+i}>')
                cfg.append(f'    <P{404+i}>{line.device_line_auth_id or line.device_line_username}</P{404+i}>')
                cfg.append(f'    <P{8+i}>{line.device_line_password}</P{8+i}>')
                cfg.append(f'    <P{23+i}>{line.device_line_display_name}</P{23+i}>')
            cfg += ['  </config>', '</gs_provision>']
            return '\\n'.join(cfg)

        def _polycom_config(self, device, lines):
            cfg = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>', '<APPLICATION>']
            for i, line in enumerate(lines, 1):
                cfg.append(f'  <REG reg.1.address="{line.device_line_username}"')
                cfg.append(f'       reg.1.auth.userId="{line.device_line_auth_id or line.device_line_username}"')
                cfg.append(f'       reg.1.auth.password="{line.device_line_password}"')
                cfg.append(f'       reg.1.server.1.address="{line.device_line_server_address}" />')
            cfg.append('</APPLICATION>')
            return '\\n'.join(cfg)

        def _generic_config(self, device, lines):
            cfg = [f'# Generic provisioning config for {device.device_vendor} {device.device_mac_address}']
            for i, line in enumerate(lines, 1):
                cfg.append(f'line{i}_server={line.device_line_server_address}')
                cfg.append(f'line{i}_user={line.device_line_username}')
                cfg.append(f'line{i}_pass={line.device_line_password}')
            return '\\n'.join(cfg)
""")

write(os.path.join(d, 'urls.py'), """
    from django.urls import path
    from .views import ProvisionView

    urlpatterns = [
        path('<str:mac>/', ProvisionView.as_view(), name='provision'),
    ]
""")

write(os.path.join(d, 'admin.py'), "# No models in provision app\n")

print('All fifth-batch apps done!')
