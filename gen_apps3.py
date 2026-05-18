#!/usr/bin/env python3
"""
gen_apps3.py - devices, recordings, ivr_menus, call_flows, time_conditions,
               destinations, feature_codes, access_controls
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

# ─────────────────────────────────────────────────────────────────── devices ──
print('devices...')
make_app('devices')
d = os.path.join(BASE, 'devices')

write(os.path.join(d, 'models.py'), """
    import uuid
    from django.db import models
    from core.models import Domain

    class Device(models.Model):
        device_uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
        domain = models.ForeignKey(Domain, on_delete=models.CASCADE, null=True, blank=True, db_column='domain_uuid')
        device_label = models.CharField(max_length=255, blank=True)
        device_mac_address = models.CharField(max_length=255, blank=True)
        device_vendor = models.CharField(max_length=255, blank=True)
        device_model = models.CharField(max_length=255, blank=True)
        device_firmware_version = models.CharField(max_length=255, blank=True)
        device_profile_uuid = models.UUIDField(null=True, blank=True)
        device_enabled = models.BooleanField(default=True)
        device_enabled_date = models.DateTimeField(null=True, blank=True)
        device_description = models.TextField(blank=True)
        insert_date = models.DateTimeField(auto_now_add=True)
        insert_user = models.UUIDField(null=True, blank=True)
        update_date = models.DateTimeField(auto_now=True)
        update_user = models.UUIDField(null=True, blank=True)

        class Meta:
            db_table = 'v_devices'

        def __str__(self):
            return f'{self.device_mac_address} ({self.device_vendor})'

    class DeviceLine(models.Model):
        device_line_uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
        device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name='lines', db_column='device_uuid')
        domain = models.ForeignKey(Domain, on_delete=models.CASCADE, null=True, blank=True, db_column='domain_uuid')
        line_number = models.IntegerField(default=1)
        device_line_server_address = models.CharField(max_length=255, blank=True)
        device_line_label = models.CharField(max_length=255, blank=True)
        device_line_username = models.CharField(max_length=255, blank=True)
        device_line_password = models.CharField(max_length=255, blank=True)
        device_line_auth_id = models.CharField(max_length=255, blank=True)
        device_line_extension = models.CharField(max_length=255, blank=True)
        device_line_display_name = models.CharField(max_length=255, blank=True)
        device_line_enabled = models.BooleanField(default=True)
        insert_date = models.DateTimeField(auto_now_add=True)
        insert_user = models.UUIDField(null=True, blank=True)

        class Meta:
            db_table = 'v_device_lines'
            ordering = ['line_number']

    class DeviceSetting(models.Model):
        device_setting_uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
        device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name='settings', db_column='device_uuid')
        domain = models.ForeignKey(Domain, on_delete=models.CASCADE, null=True, blank=True, db_column='domain_uuid')
        device_setting_name = models.CharField(max_length=255)
        device_setting_value = models.TextField(blank=True)
        device_setting_enabled = models.BooleanField(default=True)
        device_setting_description = models.TextField(blank=True)

        class Meta:
            db_table = 'v_device_settings'
""")

write(os.path.join(d, 'serializers.py'), """
    from rest_framework import serializers
    from .models import Device, DeviceLine, DeviceSetting

    class DeviceLineSerializer(serializers.ModelSerializer):
        class Meta:
            model = DeviceLine
            fields = '__all__'
            read_only_fields = ['device_line_uuid', 'insert_date', 'insert_user']

    class DeviceSettingSerializer(serializers.ModelSerializer):
        class Meta:
            model = DeviceSetting
            fields = '__all__'
            read_only_fields = ['device_setting_uuid']

    class DeviceSerializer(serializers.ModelSerializer):
        lines = DeviceLineSerializer(many=True, read_only=True)
        settings = DeviceSettingSerializer(many=True, read_only=True)

        class Meta:
            model = Device
            fields = '__all__'
            read_only_fields = ['device_uuid', 'insert_date', 'insert_user', 'update_date', 'update_user']

    class DeviceListSerializer(serializers.ModelSerializer):
        class Meta:
            model = Device
            fields = ['device_uuid', 'device_mac_address', 'device_label', 'device_vendor', 'device_model', 'device_enabled']
""")

write(os.path.join(d, 'views.py'), """
    from rest_framework import viewsets, filters
    from rest_framework.decorators import action
    from rest_framework.response import Response
    from django_filters.rest_framework import DjangoFilterBackend
    from .models import Device, DeviceLine, DeviceSetting
    from .serializers import DeviceSerializer, DeviceListSerializer, DeviceLineSerializer, DeviceSettingSerializer

    class DeviceViewSet(viewsets.ModelViewSet):
        queryset = Device.objects.all().prefetch_related('lines', 'settings')
        serializer_class = DeviceSerializer
        filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
        filterset_fields = ['domain', 'device_vendor', 'device_model', 'device_enabled']
        search_fields = ['device_mac_address', 'device_label', 'device_vendor']
        ordering_fields = ['device_mac_address', 'device_vendor', 'device_model']

        def get_queryset(self):
            qs = super().get_queryset()
            domain = self.request.query_params.get('domain_uuid')
            if domain:
                qs = qs.filter(domain__domain_uuid=domain)
            return qs

        def get_serializer_class(self):
            if self.action == 'list':
                return DeviceListSerializer
            return DeviceSerializer

    class DeviceLineViewSet(viewsets.ModelViewSet):
        queryset = DeviceLine.objects.all()
        serializer_class = DeviceLineSerializer
        filter_backends = [DjangoFilterBackend]
        filterset_fields = ['device']

    class DeviceSettingViewSet(viewsets.ModelViewSet):
        queryset = DeviceSetting.objects.all()
        serializer_class = DeviceSettingSerializer
        filter_backends = [DjangoFilterBackend]
        filterset_fields = ['device']
""")

write(os.path.join(d, 'urls.py'), """
    from rest_framework.routers import DefaultRouter
    from .views import DeviceViewSet, DeviceLineViewSet, DeviceSettingViewSet

    router = DefaultRouter()
    router.register(r'', DeviceViewSet, basename='device')
    router.register(r'lines', DeviceLineViewSet, basename='device-line')
    router.register(r'device-settings', DeviceSettingViewSet, basename='device-setting')
    urlpatterns = router.urls
""")

write(os.path.join(d, 'admin.py'), """
    from django.contrib import admin
    from .models import Device, DeviceLine, DeviceSetting

    class DeviceLineInline(admin.TabularInline):
        model = DeviceLine
        extra = 1

    class DeviceSettingInline(admin.TabularInline):
        model = DeviceSetting
        extra = 0

    @admin.register(Device)
    class DeviceAdmin(admin.ModelAdmin):
        list_display = ['device_mac_address', 'device_vendor', 'device_model', 'device_label', 'device_enabled']
        list_filter = ['device_vendor', 'device_enabled']
        search_fields = ['device_mac_address', 'device_label']
        inlines = [DeviceLineInline, DeviceSettingInline]
""")

# ──────────────────────────────────────────────────────────────── recordings ──
print('recordings...')
make_app('recordings')
d = os.path.join(BASE, 'recordings')

write(os.path.join(d, 'models.py'), """
    import uuid
    from django.db import models
    from core.models import Domain

    class Recording(models.Model):
        recording_uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
        domain = models.ForeignKey(Domain, on_delete=models.CASCADE, null=True, blank=True, db_column='domain_uuid')
        recording_name = models.CharField(max_length=255)
        recording_filename = models.CharField(max_length=255)
        recording_description = models.TextField(blank=True)
        recording_base64 = models.TextField(blank=True)
        insert_date = models.DateTimeField(auto_now_add=True)
        insert_user = models.UUIDField(null=True, blank=True)
        update_date = models.DateTimeField(auto_now=True)
        update_user = models.UUIDField(null=True, blank=True)

        class Meta:
            db_table = 'v_recordings'

        def __str__(self):
            return self.recording_name

    class CallRecording(models.Model):
        call_recording_uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
        domain = models.ForeignKey(Domain, on_delete=models.CASCADE, null=True, blank=True, db_column='domain_uuid')
        call_recording_filename = models.CharField(max_length=512)
        call_recording_caller_id_name = models.CharField(max_length=255, blank=True)
        call_recording_caller_id_number = models.CharField(max_length=255, blank=True)
        call_recording_destination_number = models.CharField(max_length=255, blank=True)
        call_recording_start_stamp = models.DateTimeField(null=True, blank=True)
        call_recording_duration = models.IntegerField(default=0)
        call_recording_billsec = models.IntegerField(default=0)
        insert_date = models.DateTimeField(auto_now_add=True)

        class Meta:
            db_table = 'v_call_recordings'
            ordering = ['-insert_date']
""")

write(os.path.join(d, 'serializers.py'), """
    from rest_framework import serializers
    from .models import Recording, CallRecording

    class RecordingSerializer(serializers.ModelSerializer):
        class Meta:
            model = Recording
            fields = '__all__'
            read_only_fields = ['recording_uuid', 'insert_date', 'insert_user', 'update_date', 'update_user']

    class CallRecordingSerializer(serializers.ModelSerializer):
        class Meta:
            model = CallRecording
            fields = '__all__'
            read_only_fields = ['call_recording_uuid', 'insert_date']
""")

write(os.path.join(d, 'views.py'), """
    from rest_framework import viewsets, filters
    from django_filters.rest_framework import DjangoFilterBackend
    from .models import Recording, CallRecording
    from .serializers import RecordingSerializer, CallRecordingSerializer

    class RecordingViewSet(viewsets.ModelViewSet):
        queryset = Recording.objects.all()
        serializer_class = RecordingSerializer
        filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
        filterset_fields = ['domain']
        search_fields = ['recording_name', 'recording_filename']
        ordering_fields = ['recording_name', 'insert_date']

        def get_queryset(self):
            qs = super().get_queryset()
            domain = self.request.query_params.get('domain_uuid')
            if domain:
                qs = qs.filter(domain__domain_uuid=domain)
            return qs

    class CallRecordingViewSet(viewsets.ReadOnlyModelViewSet):
        queryset = CallRecording.objects.all()
        serializer_class = CallRecordingSerializer
        filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
        filterset_fields = ['domain']
        search_fields = ['call_recording_caller_id_number', 'call_recording_destination_number']
        ordering_fields = ['call_recording_start_stamp', 'insert_date']
""")

write(os.path.join(d, 'urls.py'), """
    from rest_framework.routers import DefaultRouter
    from .views import RecordingViewSet, CallRecordingViewSet

    router = DefaultRouter()
    router.register(r'', RecordingViewSet, basename='recording')
    router.register(r'call-recordings', CallRecordingViewSet, basename='call-recording')
    urlpatterns = router.urls
""")

write(os.path.join(d, 'admin.py'), """
    from django.contrib import admin
    from .models import Recording, CallRecording

    @admin.register(Recording)
    class RecordingAdmin(admin.ModelAdmin):
        list_display = ['recording_name', 'recording_filename', 'insert_date']
        search_fields = ['recording_name', 'recording_filename']

    @admin.register(CallRecording)
    class CallRecordingAdmin(admin.ModelAdmin):
        list_display = ['call_recording_caller_id_number', 'call_recording_destination_number',
                        'call_recording_duration', 'call_recording_start_stamp']
        list_filter = ['domain']
""")

# ──────────────────────────────────────────────────────────────── ivr_menus ──
print('ivr_menus...')
make_app('ivr_menus')
d = os.path.join(BASE, 'ivr_menus')

write(os.path.join(d, 'models.py'), """
    import uuid
    from django.db import models
    from core.models import Domain

    class IvrMenu(models.Model):
        ivr_menu_uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
        domain = models.ForeignKey(Domain, on_delete=models.CASCADE, null=True, blank=True, db_column='domain_uuid')
        ivr_menu_name = models.CharField(max_length=255)
        ivr_menu_extension = models.CharField(max_length=255, blank=True)
        ivr_menu_language = models.CharField(max_length=10, default='en')
        ivr_menu_greet_long = models.CharField(max_length=255, blank=True)
        ivr_menu_greet_short = models.CharField(max_length=255, blank=True)
        ivr_menu_invalid_sound = models.CharField(max_length=255, blank=True)
        ivr_menu_exit_sound = models.CharField(max_length=255, blank=True)
        ivr_menu_confirm_macro = models.CharField(max_length=255, blank=True)
        ivr_menu_confirm_key = models.CharField(max_length=10, blank=True)
        ivr_menu_tts_engine = models.CharField(max_length=64, blank=True)
        ivr_menu_tts_voice = models.CharField(max_length=64, blank=True)
        ivr_menu_confirm_attempts = models.IntegerField(default=3)
        ivr_menu_timeout = models.IntegerField(default=3000)
        ivr_menu_inter_digit_timeout = models.IntegerField(default=2000)
        ivr_menu_max_failures = models.IntegerField(default=3)
        ivr_menu_max_timeouts = models.IntegerField(default=3)
        ivr_menu_digit_len = models.IntegerField(default=4)
        ivr_menu_direct_dial = models.CharField(max_length=10, blank=True)
        ivr_menu_ringback = models.CharField(max_length=255, blank=True)
        ivr_menu_cid_prefix = models.CharField(max_length=64, blank=True)
        ivr_menu_enabled = models.BooleanField(default=True)
        ivr_menu_description = models.TextField(blank=True)
        insert_date = models.DateTimeField(auto_now_add=True)
        insert_user = models.UUIDField(null=True, blank=True)
        update_date = models.DateTimeField(auto_now=True)
        update_user = models.UUIDField(null=True, blank=True)

        class Meta:
            db_table = 'v_ivr_menus'

        def __str__(self):
            return self.ivr_menu_name

    class IvrMenuOption(models.Model):
        ivr_menu_option_uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
        ivr_menu = models.ForeignKey(IvrMenu, on_delete=models.CASCADE, related_name='options', db_column='ivr_menu_uuid')
        domain = models.ForeignKey(Domain, on_delete=models.CASCADE, null=True, blank=True, db_column='domain_uuid')
        ivr_menu_option_digits = models.CharField(max_length=64)
        ivr_menu_option_action = models.CharField(max_length=64, blank=True)
        ivr_menu_option_param = models.CharField(max_length=255, blank=True)
        ivr_menu_option_order = models.IntegerField(default=900)
        ivr_menu_option_description = models.TextField(blank=True)
        insert_date = models.DateTimeField(auto_now_add=True)
        insert_user = models.UUIDField(null=True, blank=True)

        class Meta:
            db_table = 'v_ivr_menu_options'
            ordering = ['ivr_menu_option_order']
""")

write(os.path.join(d, 'serializers.py'), """
    from rest_framework import serializers
    from .models import IvrMenu, IvrMenuOption

    class IvrMenuOptionSerializer(serializers.ModelSerializer):
        class Meta:
            model = IvrMenuOption
            fields = '__all__'
            read_only_fields = ['ivr_menu_option_uuid', 'insert_date', 'insert_user']

    class IvrMenuSerializer(serializers.ModelSerializer):
        options = IvrMenuOptionSerializer(many=True, read_only=True)

        class Meta:
            model = IvrMenu
            fields = '__all__'
            read_only_fields = ['ivr_menu_uuid', 'insert_date', 'insert_user', 'update_date', 'update_user']

    class IvrMenuListSerializer(serializers.ModelSerializer):
        class Meta:
            model = IvrMenu
            fields = ['ivr_menu_uuid', 'ivr_menu_name', 'ivr_menu_extension', 'ivr_menu_enabled']
""")

write(os.path.join(d, 'views.py'), """
    from rest_framework import viewsets, filters
    from django_filters.rest_framework import DjangoFilterBackend
    from .models import IvrMenu, IvrMenuOption
    from .serializers import IvrMenuSerializer, IvrMenuListSerializer, IvrMenuOptionSerializer

    class IvrMenuViewSet(viewsets.ModelViewSet):
        queryset = IvrMenu.objects.all().prefetch_related('options')
        serializer_class = IvrMenuSerializer
        filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
        filterset_fields = ['domain', 'ivr_menu_enabled']
        search_fields = ['ivr_menu_name', 'ivr_menu_extension']
        ordering_fields = ['ivr_menu_name', 'ivr_menu_extension']

        def get_queryset(self):
            qs = super().get_queryset()
            domain = self.request.query_params.get('domain_uuid')
            if domain:
                qs = qs.filter(domain__domain_uuid=domain)
            return qs

        def get_serializer_class(self):
            if self.action == 'list':
                return IvrMenuListSerializer
            return IvrMenuSerializer

    class IvrMenuOptionViewSet(viewsets.ModelViewSet):
        queryset = IvrMenuOption.objects.all()
        serializer_class = IvrMenuOptionSerializer
        filter_backends = [DjangoFilterBackend]
        filterset_fields = ['ivr_menu']
""")

write(os.path.join(d, 'urls.py'), """
    from rest_framework.routers import DefaultRouter
    from .views import IvrMenuViewSet, IvrMenuOptionViewSet

    router = DefaultRouter()
    router.register(r'', IvrMenuViewSet, basename='ivr-menu')
    router.register(r'options', IvrMenuOptionViewSet, basename='ivr-menu-option')
    urlpatterns = router.urls
""")

write(os.path.join(d, 'admin.py'), """
    from django.contrib import admin
    from .models import IvrMenu, IvrMenuOption

    class IvrMenuOptionInline(admin.TabularInline):
        model = IvrMenuOption
        extra = 1

    @admin.register(IvrMenu)
    class IvrMenuAdmin(admin.ModelAdmin):
        list_display = ['ivr_menu_name', 'ivr_menu_extension', 'ivr_menu_enabled']
        list_filter = ['ivr_menu_enabled']
        search_fields = ['ivr_menu_name']
        inlines = [IvrMenuOptionInline]
""")

# ──────────────────────────────────────────────────────────────── call_flows ──
print('call_flows...')
make_app('call_flows')
d = os.path.join(BASE, 'call_flows')

write(os.path.join(d, 'models.py'), """
    import uuid
    from django.db import models
    from core.models import Domain

    class CallFlow(models.Model):
        call_flow_uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
        domain = models.ForeignKey(Domain, on_delete=models.CASCADE, null=True, blank=True, db_column='domain_uuid')
        call_flow_name = models.CharField(max_length=255)
        call_flow_extension = models.CharField(max_length=255, blank=True)
        call_flow_feature_code = models.CharField(max_length=50, blank=True)
        call_flow_status = models.CharField(max_length=10, default='true')
        call_flow_sound = models.CharField(max_length=255, blank=True)
        call_flow_greeting = models.CharField(max_length=255, blank=True)
        call_flow_context = models.CharField(max_length=128, blank=True)
        call_flow_enabled = models.BooleanField(default=True)
        call_flow_description = models.TextField(blank=True)
        insert_date = models.DateTimeField(auto_now_add=True)
        insert_user = models.UUIDField(null=True, blank=True)
        update_date = models.DateTimeField(auto_now=True)
        update_user = models.UUIDField(null=True, blank=True)

        class Meta:
            db_table = 'v_call_flows'

        def __str__(self):
            return self.call_flow_name

    class CallFlowOption(models.Model):
        call_flow_option_uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
        call_flow = models.ForeignKey(CallFlow, on_delete=models.CASCADE, related_name='options', db_column='call_flow_uuid')
        domain = models.ForeignKey(Domain, on_delete=models.CASCADE, null=True, blank=True, db_column='domain_uuid')
        call_flow_option_order = models.IntegerField(default=0)
        call_flow_option_enabled = models.BooleanField(default=True)
        call_flow_option_destination = models.CharField(max_length=255, blank=True)
        call_flow_option_app = models.CharField(max_length=128, blank=True)
        call_flow_option_param = models.CharField(max_length=255, blank=True)
        insert_date = models.DateTimeField(auto_now_add=True)

        class Meta:
            db_table = 'v_call_flow_options'
            ordering = ['call_flow_option_order']
""")

write(os.path.join(d, 'serializers.py'), """
    from rest_framework import serializers
    from .models import CallFlow, CallFlowOption

    class CallFlowOptionSerializer(serializers.ModelSerializer):
        class Meta:
            model = CallFlowOption
            fields = '__all__'
            read_only_fields = ['call_flow_option_uuid', 'insert_date']

    class CallFlowSerializer(serializers.ModelSerializer):
        options = CallFlowOptionSerializer(many=True, read_only=True)

        class Meta:
            model = CallFlow
            fields = '__all__'
            read_only_fields = ['call_flow_uuid', 'insert_date', 'insert_user', 'update_date', 'update_user']

    class CallFlowListSerializer(serializers.ModelSerializer):
        class Meta:
            model = CallFlow
            fields = ['call_flow_uuid', 'call_flow_name', 'call_flow_extension', 'call_flow_status', 'call_flow_enabled']
""")

write(os.path.join(d, 'views.py'), """
    from rest_framework import viewsets, filters, status
    from rest_framework.decorators import action
    from rest_framework.response import Response
    from django_filters.rest_framework import DjangoFilterBackend
    from .models import CallFlow, CallFlowOption
    from .serializers import CallFlowSerializer, CallFlowListSerializer, CallFlowOptionSerializer

    class CallFlowViewSet(viewsets.ModelViewSet):
        queryset = CallFlow.objects.all().prefetch_related('options')
        serializer_class = CallFlowSerializer
        filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
        filterset_fields = ['domain', 'call_flow_enabled']
        search_fields = ['call_flow_name', 'call_flow_extension']
        ordering_fields = ['call_flow_name']

        def get_queryset(self):
            qs = super().get_queryset()
            domain = self.request.query_params.get('domain_uuid')
            if domain:
                qs = qs.filter(domain__domain_uuid=domain)
            return qs

        def get_serializer_class(self):
            if self.action == 'list':
                return CallFlowListSerializer
            return CallFlowSerializer

        @action(detail=True, methods=['post'])
        def toggle(self, request, pk=None):
            cf = self.get_object()
            cf.call_flow_status = 'false' if cf.call_flow_status == 'true' else 'true'
            cf.save(update_fields=['call_flow_status'])
            return Response({'status': cf.call_flow_status})

    class CallFlowOptionViewSet(viewsets.ModelViewSet):
        queryset = CallFlowOption.objects.all()
        serializer_class = CallFlowOptionSerializer
        filter_backends = [DjangoFilterBackend]
        filterset_fields = ['call_flow']
""")

write(os.path.join(d, 'urls.py'), """
    from rest_framework.routers import DefaultRouter
    from .views import CallFlowViewSet, CallFlowOptionViewSet

    router = DefaultRouter()
    router.register(r'', CallFlowViewSet, basename='call-flow')
    router.register(r'options', CallFlowOptionViewSet, basename='call-flow-option')
    urlpatterns = router.urls
""")

write(os.path.join(d, 'admin.py'), """
    from django.contrib import admin
    from .models import CallFlow, CallFlowOption

    class CallFlowOptionInline(admin.TabularInline):
        model = CallFlowOption
        extra = 1

    @admin.register(CallFlow)
    class CallFlowAdmin(admin.ModelAdmin):
        list_display = ['call_flow_name', 'call_flow_extension', 'call_flow_status', 'call_flow_enabled']
        list_filter = ['call_flow_enabled']
        search_fields = ['call_flow_name']
        inlines = [CallFlowOptionInline]
""")

# ─────────────────────────────────────────────────────────── time_conditions ──
print('time_conditions...')
make_app('time_conditions')
d = os.path.join(BASE, 'time_conditions')

write(os.path.join(d, 'models.py'), """
    import uuid
    from django.db import models
    from core.models import Domain

    class TimeCondition(models.Model):
        dialplan_uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
        domain = models.ForeignKey(Domain, on_delete=models.CASCADE, null=True, blank=True, db_column='domain_uuid')
        dialplan_name = models.CharField(max_length=255)
        dialplan_extension = models.CharField(max_length=255, blank=True)
        dialplan_context = models.CharField(max_length=128, blank=True)
        dialplan_enabled = models.BooleanField(default=True)
        dialplan_description = models.TextField(blank=True)
        insert_date = models.DateTimeField(auto_now_add=True)
        insert_user = models.UUIDField(null=True, blank=True)
        update_date = models.DateTimeField(auto_now=True)
        update_user = models.UUIDField(null=True, blank=True)

        class Meta:
            db_table = 'v_time_conditions'

        def __str__(self):
            return self.dialplan_name

    class TimeConditionRange(models.Model):
        time_condition_uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
        dialplan = models.ForeignKey(TimeCondition, on_delete=models.CASCADE, related_name='ranges', db_column='dialplan_uuid')
        domain = models.ForeignKey(Domain, on_delete=models.CASCADE, null=True, blank=True, db_column='domain_uuid')
        time_condition_order = models.IntegerField(default=900)
        time_condition_enabled = models.BooleanField(default=True)
        # Time range criteria
        time_condition_year = models.CharField(max_length=64, blank=True)
        time_condition_yday = models.CharField(max_length=64, blank=True)
        time_condition_mon = models.CharField(max_length=64, blank=True)
        time_condition_mday = models.CharField(max_length=64, blank=True)
        time_condition_week = models.CharField(max_length=64, blank=True)
        time_condition_mweek = models.CharField(max_length=64, blank=True)
        time_condition_wday = models.CharField(max_length=64, blank=True)
        time_condition_hour = models.CharField(max_length=64, blank=True)
        time_condition_minute = models.CharField(max_length=64, blank=True)
        time_condition_minute_of_day = models.CharField(max_length=64, blank=True)
        time_condition_time_of_day = models.CharField(max_length=64, blank=True)
        time_condition_date_time = models.CharField(max_length=64, blank=True)
        # Destinations
        time_condition_destination_number = models.CharField(max_length=255, blank=True)
        time_condition_destination_action = models.CharField(max_length=64, blank=True)
        time_condition_destination_app = models.CharField(max_length=128, blank=True)
        time_condition_destination_param = models.CharField(max_length=255, blank=True)
        insert_date = models.DateTimeField(auto_now_add=True)

        class Meta:
            db_table = 'v_time_condition_ranges'
            ordering = ['time_condition_order']
""")

write(os.path.join(d, 'serializers.py'), """
    from rest_framework import serializers
    from .models import TimeCondition, TimeConditionRange

    class TimeConditionRangeSerializer(serializers.ModelSerializer):
        class Meta:
            model = TimeConditionRange
            fields = '__all__'
            read_only_fields = ['time_condition_uuid', 'insert_date']

    class TimeConditionSerializer(serializers.ModelSerializer):
        ranges = TimeConditionRangeSerializer(many=True, read_only=True)

        class Meta:
            model = TimeCondition
            fields = '__all__'
            read_only_fields = ['dialplan_uuid', 'insert_date', 'insert_user', 'update_date', 'update_user']

    class TimeConditionListSerializer(serializers.ModelSerializer):
        class Meta:
            model = TimeCondition
            fields = ['dialplan_uuid', 'dialplan_name', 'dialplan_extension', 'dialplan_enabled']
""")

write(os.path.join(d, 'views.py'), """
    from rest_framework import viewsets, filters
    from django_filters.rest_framework import DjangoFilterBackend
    from .models import TimeCondition, TimeConditionRange
    from .serializers import TimeConditionSerializer, TimeConditionListSerializer, TimeConditionRangeSerializer

    class TimeConditionViewSet(viewsets.ModelViewSet):
        queryset = TimeCondition.objects.all().prefetch_related('ranges')
        serializer_class = TimeConditionSerializer
        filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
        filterset_fields = ['domain', 'dialplan_enabled']
        search_fields = ['dialplan_name', 'dialplan_extension']
        ordering_fields = ['dialplan_name']

        def get_queryset(self):
            qs = super().get_queryset()
            domain = self.request.query_params.get('domain_uuid')
            if domain:
                qs = qs.filter(domain__domain_uuid=domain)
            return qs

        def get_serializer_class(self):
            if self.action == 'list':
                return TimeConditionListSerializer
            return TimeConditionSerializer

    class TimeConditionRangeViewSet(viewsets.ModelViewSet):
        queryset = TimeConditionRange.objects.all()
        serializer_class = TimeConditionRangeSerializer
        filter_backends = [DjangoFilterBackend]
        filterset_fields = ['dialplan']
""")

write(os.path.join(d, 'urls.py'), """
    from rest_framework.routers import DefaultRouter
    from .views import TimeConditionViewSet, TimeConditionRangeViewSet

    router = DefaultRouter()
    router.register(r'', TimeConditionViewSet, basename='time-condition')
    router.register(r'ranges', TimeConditionRangeViewSet, basename='time-condition-range')
    urlpatterns = router.urls
""")

write(os.path.join(d, 'admin.py'), """
    from django.contrib import admin
    from .models import TimeCondition, TimeConditionRange

    class TimeConditionRangeInline(admin.TabularInline):
        model = TimeConditionRange
        extra = 1

    @admin.register(TimeCondition)
    class TimeConditionAdmin(admin.ModelAdmin):
        list_display = ['dialplan_name', 'dialplan_extension', 'dialplan_enabled']
        list_filter = ['dialplan_enabled']
        search_fields = ['dialplan_name']
        inlines = [TimeConditionRangeInline]
""")

# ──────────────────────────────────────────────────────────────── destinations ──
print('destinations...')
make_app('destinations')
d = os.path.join(BASE, 'destinations')

write(os.path.join(d, 'models.py'), """
    import uuid
    from django.db import models
    from core.models import Domain

    class Destination(models.Model):
        destination_uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
        domain = models.ForeignKey(Domain, on_delete=models.CASCADE, null=True, blank=True, db_column='domain_uuid')
        dialplan_uuid = models.UUIDField(null=True, blank=True)
        destination_type = models.CharField(max_length=32, default='inbound')
        destination_number = models.CharField(max_length=255)
        destination_number_regex = models.CharField(max_length=255, blank=True)
        destination_caller_id_name = models.CharField(max_length=255, blank=True)
        destination_caller_id_number = models.CharField(max_length=255, blank=True)
        destination_cid_name_prefix = models.CharField(max_length=255, blank=True)
        destination_context = models.CharField(max_length=128, blank=True)
        destination_app = models.CharField(max_length=128, blank=True)
        destination_data = models.CharField(max_length=512, blank=True)
        destination_bridge = models.TextField(blank=True)
        destination_ringback = models.CharField(max_length=255, blank=True)
        destination_hold_music = models.CharField(max_length=255, blank=True)
        destination_record = models.BooleanField(default=False)
        destination_accountcode = models.CharField(max_length=255, blank=True)
        destination_enabled = models.BooleanField(default=True)
        destination_description = models.TextField(blank=True)
        insert_date = models.DateTimeField(auto_now_add=True)
        insert_user = models.UUIDField(null=True, blank=True)
        update_date = models.DateTimeField(auto_now=True)
        update_user = models.UUIDField(null=True, blank=True)

        class Meta:
            db_table = 'v_destinations'

        def __str__(self):
            return f'{self.destination_number} ({self.destination_type})'
""")

write(os.path.join(d, 'serializers.py'), """
    from rest_framework import serializers
    from .models import Destination

    class DestinationSerializer(serializers.ModelSerializer):
        class Meta:
            model = Destination
            fields = '__all__'
            read_only_fields = ['destination_uuid', 'insert_date', 'insert_user', 'update_date', 'update_user']

    class DestinationListSerializer(serializers.ModelSerializer):
        class Meta:
            model = Destination
            fields = ['destination_uuid', 'destination_number', 'destination_type', 'destination_context', 'destination_enabled']
""")

write(os.path.join(d, 'views.py'), """
    from rest_framework import viewsets, filters
    from django_filters.rest_framework import DjangoFilterBackend
    from .models import Destination
    from .serializers import DestinationSerializer, DestinationListSerializer

    class DestinationViewSet(viewsets.ModelViewSet):
        queryset = Destination.objects.all()
        serializer_class = DestinationSerializer
        filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
        filterset_fields = ['domain', 'destination_type', 'destination_enabled']
        search_fields = ['destination_number', 'destination_caller_id_number']
        ordering_fields = ['destination_number', 'destination_type', 'insert_date']

        def get_queryset(self):
            qs = super().get_queryset()
            domain = self.request.query_params.get('domain_uuid')
            if domain:
                qs = qs.filter(domain__domain_uuid=domain)
            return qs

        def get_serializer_class(self):
            if self.action == 'list':
                return DestinationListSerializer
            return DestinationSerializer
""")

write(os.path.join(d, 'urls.py'), """
    from rest_framework.routers import DefaultRouter
    from .views import DestinationViewSet

    router = DefaultRouter()
    router.register(r'', DestinationViewSet, basename='destination')
    urlpatterns = router.urls
""")

write(os.path.join(d, 'admin.py'), """
    from django.contrib import admin
    from .models import Destination

    @admin.register(Destination)
    class DestinationAdmin(admin.ModelAdmin):
        list_display = ['destination_number', 'destination_type', 'destination_context', 'destination_enabled']
        list_filter = ['destination_type', 'destination_enabled']
        search_fields = ['destination_number']
""")

# ─────────────────────────────────────────────────────────── feature_codes ──
print('feature_codes...')
make_app('feature_codes')
d = os.path.join(BASE, 'feature_codes')

write(os.path.join(d, 'models.py'), """
    import uuid
    from django.db import models
    from core.models import Domain

    class FeatureCode(models.Model):
        feature_code_uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
        domain = models.ForeignKey(Domain, on_delete=models.CASCADE, null=True, blank=True, db_column='domain_uuid')
        dialplan_uuid = models.UUIDField(null=True, blank=True)
        feature_code_name = models.CharField(max_length=255)
        feature_code_description = models.TextField(blank=True)
        insert_date = models.DateTimeField(auto_now_add=True)
        insert_user = models.UUIDField(null=True, blank=True)
        update_date = models.DateTimeField(auto_now=True)
        update_user = models.UUIDField(null=True, blank=True)

        class Meta:
            db_table = 'v_feature_codes'

        def __str__(self):
            return self.feature_code_name
""")

write(os.path.join(d, 'serializers.py'), """
    from rest_framework import serializers
    from .models import FeatureCode

    class FeatureCodeSerializer(serializers.ModelSerializer):
        class Meta:
            model = FeatureCode
            fields = '__all__'
            read_only_fields = ['feature_code_uuid', 'insert_date', 'insert_user', 'update_date', 'update_user']
""")

write(os.path.join(d, 'views.py'), """
    from rest_framework import viewsets, filters
    from django_filters.rest_framework import DjangoFilterBackend
    from .models import FeatureCode
    from .serializers import FeatureCodeSerializer

    class FeatureCodeViewSet(viewsets.ModelViewSet):
        queryset = FeatureCode.objects.all()
        serializer_class = FeatureCodeSerializer
        filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
        filterset_fields = ['domain']
        search_fields = ['feature_code_name']
        ordering_fields = ['feature_code_name']

        def get_queryset(self):
            qs = super().get_queryset()
            domain = self.request.query_params.get('domain_uuid')
            if domain:
                qs = qs.filter(domain__domain_uuid=domain)
            return qs
""")

write(os.path.join(d, 'urls.py'), """
    from rest_framework.routers import DefaultRouter
    from .views import FeatureCodeViewSet

    router = DefaultRouter()
    router.register(r'', FeatureCodeViewSet, basename='feature-code')
    urlpatterns = router.urls
""")

write(os.path.join(d, 'admin.py'), """
    from django.contrib import admin
    from .models import FeatureCode

    @admin.register(FeatureCode)
    class FeatureCodeAdmin(admin.ModelAdmin):
        list_display = ['feature_code_name']
        search_fields = ['feature_code_name']
""")

# ─────────────────────────────────────────────────────────── access_controls ──
print('access_controls...')
make_app('access_controls')
d = os.path.join(BASE, 'access_controls')

write(os.path.join(d, 'models.py'), """
    import uuid
    from django.db import models
    from core.models import Domain

    class AccessControl(models.Model):
        ACCESS_DEFAULT_ACTIONS = [('allow', 'Allow'), ('deny', 'Deny')]

        access_control_uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
        domain = models.ForeignKey(Domain, on_delete=models.CASCADE, null=True, blank=True, db_column='domain_uuid')
        access_control_name = models.CharField(max_length=255)
        access_control_default = models.CharField(max_length=10, choices=ACCESS_DEFAULT_ACTIONS, default='deny')
        access_control_description = models.TextField(blank=True)
        insert_date = models.DateTimeField(auto_now_add=True)
        insert_user = models.UUIDField(null=True, blank=True)
        update_date = models.DateTimeField(auto_now=True)
        update_user = models.UUIDField(null=True, blank=True)

        class Meta:
            db_table = 'v_access_controls'

        def __str__(self):
            return self.access_control_name

    class AccessControlNode(models.Model):
        NODE_TYPES = [('allow', 'Allow'), ('deny', 'Deny')]

        access_control_node_uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
        access_control = models.ForeignKey(AccessControl, on_delete=models.CASCADE, related_name='nodes', db_column='access_control_uuid')
        domain = models.ForeignKey(Domain, on_delete=models.CASCADE, null=True, blank=True, db_column='domain_uuid')
        access_control_node_type = models.CharField(max_length=10, choices=NODE_TYPES, default='allow')
        access_control_node_cidr = models.CharField(max_length=255)
        access_control_node_domain = models.CharField(max_length=255, blank=True)
        access_control_node_description = models.TextField(blank=True)
        insert_date = models.DateTimeField(auto_now_add=True)
        insert_user = models.UUIDField(null=True, blank=True)

        class Meta:
            db_table = 'v_access_control_nodes'
""")

write(os.path.join(d, 'serializers.py'), """
    from rest_framework import serializers
    from .models import AccessControl, AccessControlNode

    class AccessControlNodeSerializer(serializers.ModelSerializer):
        class Meta:
            model = AccessControlNode
            fields = '__all__'
            read_only_fields = ['access_control_node_uuid', 'insert_date', 'insert_user']

    class AccessControlSerializer(serializers.ModelSerializer):
        nodes = AccessControlNodeSerializer(many=True, read_only=True)

        class Meta:
            model = AccessControl
            fields = '__all__'
            read_only_fields = ['access_control_uuid', 'insert_date', 'insert_user', 'update_date', 'update_user']

    class AccessControlListSerializer(serializers.ModelSerializer):
        node_count = serializers.SerializerMethodField()

        class Meta:
            model = AccessControl
            fields = ['access_control_uuid', 'access_control_name', 'access_control_default', 'node_count']

        def get_node_count(self, obj):
            return obj.nodes.count()
""")

write(os.path.join(d, 'views.py'), """
    from rest_framework import viewsets, filters, status
    from rest_framework.decorators import action
    from rest_framework.response import Response
    from django_filters.rest_framework import DjangoFilterBackend
    from .models import AccessControl, AccessControlNode
    from .serializers import AccessControlSerializer, AccessControlListSerializer, AccessControlNodeSerializer
    from esl.tasks import reload_xml

    class AccessControlViewSet(viewsets.ModelViewSet):
        queryset = AccessControl.objects.all().prefetch_related('nodes')
        serializer_class = AccessControlSerializer
        filter_backends = [DjangoFilterBackend, filters.SearchFilter]
        filterset_fields = ['domain']
        search_fields = ['access_control_name']

        def get_queryset(self):
            qs = super().get_queryset()
            domain = self.request.query_params.get('domain_uuid')
            if domain:
                qs = qs.filter(domain__domain_uuid=domain)
            return qs

        def get_serializer_class(self):
            if self.action == 'list':
                return AccessControlListSerializer
            return AccessControlSerializer

        @action(detail=False, methods=['post'])
        def reload(self, request):
            reload_xml.delay()
            return Response({'status': 'ACL reload queued'})

    class AccessControlNodeViewSet(viewsets.ModelViewSet):
        queryset = AccessControlNode.objects.all()
        serializer_class = AccessControlNodeSerializer
        filter_backends = [DjangoFilterBackend]
        filterset_fields = ['access_control']
""")

write(os.path.join(d, 'urls.py'), """
    from rest_framework.routers import DefaultRouter
    from .views import AccessControlViewSet, AccessControlNodeViewSet

    router = DefaultRouter()
    router.register(r'', AccessControlViewSet, basename='access-control')
    router.register(r'nodes', AccessControlNodeViewSet, basename='access-control-node')
    urlpatterns = router.urls
""")

write(os.path.join(d, 'admin.py'), """
    from django.contrib import admin
    from .models import AccessControl, AccessControlNode

    class AccessControlNodeInline(admin.TabularInline):
        model = AccessControlNode
        extra = 1

    @admin.register(AccessControl)
    class AccessControlAdmin(admin.ModelAdmin):
        list_display = ['access_control_name', 'access_control_default']
        search_fields = ['access_control_name']
        inlines = [AccessControlNodeInline]
""")

print('All third-batch apps done!')
