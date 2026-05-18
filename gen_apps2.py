"""Generate SIP profiles, call centers, conferences, CDR, devices, ring groups, and more apps."""
import os

BASE = "D:/ihspbx-django/backend"


def write(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"  WROTE {os.path.basename(path)}")


def make_app(app_name):
    app_dir = f"{BASE}/apps/{app_name}"
    mig_dir = f"{app_dir}/migrations"
    os.makedirs(app_dir, exist_ok=True)
    os.makedirs(mig_dir, exist_ok=True)
    for p in [f"{app_dir}/__init__.py", f"{mig_dir}/__init__.py"]:
        if not os.path.exists(p):
            open(p, 'w').close()
    return app_dir


def simple_urls(viewset_name, basename):
    return f"""from rest_framework.routers import DefaultRouter
from .views import {viewset_name}

router = DefaultRouter()
router.register(r'', {viewset_name}, basename='{basename}')
urlpatterns = router.urls
"""


# ─────────────────────────────────────────────────────────────────────────────
# SIP PROFILES
# ─────────────────────────────────────────────────────────────────────────────
print("sip_profiles...")
APP = make_app("sip_profiles")

write(f"{APP}/models.py", """import uuid
from django.db import models


class SipProfile(models.Model):
    sip_profile_uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sip_profile_name = models.CharField(max_length=64, unique=True)
    sip_profile_hostname = models.CharField(max_length=256, blank=True, default='')
    sip_profile_enabled = models.BooleanField(default=True)
    sip_profile_description = models.TextField(blank=True, default='')
    insert_date = models.DateTimeField(auto_now_add=True, null=True)
    insert_user = models.UUIDField(null=True, blank=True)
    update_date = models.DateTimeField(auto_now=True, null=True)
    update_user = models.UUIDField(null=True, blank=True)

    class Meta:
        db_table = 'v_sip_profiles'

    def __str__(self):
        return self.sip_profile_name


class SipProfileSetting(models.Model):
    sip_profile_setting_uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sip_profile = models.ForeignKey(SipProfile, on_delete=models.CASCADE,
                                    db_column='sip_profile_uuid', related_name='settings')
    sip_profile_setting_name = models.CharField(max_length=128)
    sip_profile_setting_value = models.TextField(blank=True, default='')
    sip_profile_setting_enabled = models.BooleanField(default=True)
    sip_profile_setting_description = models.TextField(blank=True, default='')
    insert_date = models.DateTimeField(auto_now_add=True, null=True)

    class Meta:
        db_table = 'v_sip_profile_settings'


class SipProfileDomain(models.Model):
    sip_profile_domain_uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sip_profile = models.ForeignKey(SipProfile, on_delete=models.CASCADE,
                                    db_column='sip_profile_uuid', related_name='domains')
    sip_profile_domain_name = models.CharField(max_length=128)
    sip_profile_domain_alias = models.BooleanField(default=False)
    sip_profile_domain_parse = models.BooleanField(default=False)

    class Meta:
        db_table = 'v_sip_profile_domains'
""")

write(f"{APP}/serializers.py", """from rest_framework import serializers
from .models import SipProfile, SipProfileSetting, SipProfileDomain


class SipProfileSettingSerializer(serializers.ModelSerializer):
    class Meta:
        model = SipProfileSetting
        fields = '__all__'
        read_only_fields = ['sip_profile_setting_uuid', 'insert_date']


class SipProfileDomainSerializer(serializers.ModelSerializer):
    class Meta:
        model = SipProfileDomain
        fields = '__all__'
        read_only_fields = ['sip_profile_domain_uuid']


class SipProfileSerializer(serializers.ModelSerializer):
    settings = SipProfileSettingSerializer(many=True, read_only=True)
    domains = SipProfileDomainSerializer(many=True, read_only=True)

    class Meta:
        model = SipProfile
        fields = '__all__'
        read_only_fields = ['sip_profile_uuid', 'insert_date', 'update_date']
""")

write(f"{APP}/views.py", """from rest_framework import viewsets, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import SipProfile, SipProfileSetting, SipProfileDomain
from .serializers import SipProfileSerializer, SipProfileSettingSerializer, SipProfileDomainSerializer


class SipProfileViewSet(viewsets.ModelViewSet):
    queryset = SipProfile.objects.prefetch_related('settings', 'domains')
    serializer_class = SipProfileSerializer
    permission_classes = [permissions.IsAuthenticated]
    search_fields = ['sip_profile_name', 'sip_profile_description']
    filterset_fields = ['sip_profile_enabled']

    @action(detail=True, methods=['post'])
    def reload(self, request, pk=None):
        profile = self.get_object()
        try:
            from esl.client import get_esl_client
            esl = get_esl_client()
            result = esl.sofia_reload(profile.sip_profile_name)
            return Response({'status': 'reloaded', 'result': result})
        except Exception as e:
            return Response({'error': str(e)}, status=503)

    @action(detail=True, methods=['get'])
    def status(self, request, pk=None):
        profile = self.get_object()
        try:
            from esl.client import get_esl_client
            esl = get_esl_client()
            result = esl.api(f'sofia status profile {profile.sip_profile_name}')
            return Response({'profile': profile.sip_profile_name, 'status': result})
        except Exception as e:
            return Response({'error': str(e)}, status=503)


class SipProfileSettingViewSet(viewsets.ModelViewSet):
    queryset = SipProfileSetting.objects.select_related('sip_profile')
    serializer_class = SipProfileSettingSerializer
    permission_classes = [permissions.IsAuthenticated]


class SipProfileDomainViewSet(viewsets.ModelViewSet):
    queryset = SipProfileDomain.objects.select_related('sip_profile')
    serializer_class = SipProfileDomainSerializer
    permission_classes = [permissions.IsAuthenticated]
""")

write(f"{APP}/urls.py", """from rest_framework.routers import DefaultRouter
from .views import SipProfileViewSet, SipProfileSettingViewSet, SipProfileDomainViewSet

router = DefaultRouter()
router.register(r'settings', SipProfileSettingViewSet, basename='sip-profile-setting')
router.register(r'profile-domains', SipProfileDomainViewSet, basename='sip-profile-domain')
router.register(r'', SipProfileViewSet, basename='sip-profile')
urlpatterns = router.urls
""")

write(f"{APP}/admin.py", """from django.contrib import admin
from .models import SipProfile, SipProfileSetting, SipProfileDomain

class SipProfileSettingInline(admin.TabularInline):
    model = SipProfileSetting
    extra = 0

class SipProfileDomainInline(admin.TabularInline):
    model = SipProfileDomain
    extra = 0

@admin.register(SipProfile)
class SipProfileAdmin(admin.ModelAdmin):
    list_display = ['sip_profile_name', 'sip_profile_hostname', 'sip_profile_enabled']
    list_filter = ['sip_profile_enabled']
    search_fields = ['sip_profile_name']
    inlines = [SipProfileSettingInline, SipProfileDomainInline]
""")


# ─────────────────────────────────────────────────────────────────────────────
# CALL CENTERS
# ─────────────────────────────────────────────────────────────────────────────
print("call_centers...")
APP = make_app("call_centers")

write(f"{APP}/models.py", """import uuid
from django.db import models
from core.models import Domain


class CallCenter(models.Model):
    STRATEGY_CHOICES = [
        ('ring-all','Ring All'),('longest-idle-agent','Longest Idle Agent'),
        ('round-robin','Round Robin'),('top-down','Top Down'),
        ('agent-with-least-talk-time','Least Talk Time'),
        ('agent-with-fewest-calls','Fewest Calls'),
        ('sequentially-by-agent-order','Sequential'),('random','Random'),
    ]
    queue_uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    domain = models.ForeignKey(Domain, on_delete=models.CASCADE, db_column='domain_uuid', related_name='call_centers')
    queue_name = models.CharField(max_length=128)
    queue_extension = models.CharField(max_length=32, blank=True, default='')
    queue_greet_long = models.CharField(max_length=256, blank=True, default='')
    queue_greet_short = models.CharField(max_length=256, blank=True, default='')
    queue_moh_sound = models.CharField(max_length=256, blank=True, default='')
    queue_time_base_score = models.CharField(max_length=16, default='queue')
    queue_max_wait_time = models.IntegerField(default=0)
    queue_max_wait_time_with_no_agent = models.IntegerField(default=0)
    queue_timeout_action = models.CharField(max_length=256, blank=True, default='')
    queue_discard_abandoned_after = models.IntegerField(default=900)
    queue_abandoned_resume_allowed = models.BooleanField(default=False)
    strategy = models.CharField(max_length=64, choices=STRATEGY_CHOICES, default='round-robin')
    queue_tier_rules_apply = models.BooleanField(default=False)
    queue_tier_rule_wait_second = models.IntegerField(default=300)
    queue_tier_rule_no_agent_no_wait = models.BooleanField(default=False)
    queue_tier_rule_wait_multiply_level = models.BooleanField(default=True)
    enabled = models.BooleanField(default=True)
    description = models.TextField(blank=True, default='')
    insert_date = models.DateTimeField(auto_now_add=True, null=True)
    insert_user = models.UUIDField(null=True, blank=True)
    update_date = models.DateTimeField(auto_now=True, null=True)
    update_user = models.UUIDField(null=True, blank=True)

    class Meta:
        db_table = 'v_call_center_queues'
        unique_together = [('domain', 'queue_name')]

    def __str__(self):
        return self.queue_name


class CallCenterAgent(models.Model):
    agent_uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    domain = models.ForeignKey(Domain, on_delete=models.CASCADE, db_column='domain_uuid', related_name='call_center_agents')
    agent_name = models.CharField(max_length=128)
    agent_type = models.CharField(max_length=32, default='callback',
        choices=[('callback','Callback'),('uuid-standby','UUID Standby')])
    agent_contact = models.CharField(max_length=256, blank=True, default='')
    agent_status = models.CharField(max_length=32, default='Available')
    agent_state = models.CharField(max_length=32, default='Waiting')
    max_no_answer = models.IntegerField(default=3)
    wrap_up_time = models.IntegerField(default=10)
    reject_delay_time = models.IntegerField(default=10)
    busy_delay_time = models.IntegerField(default=10)
    no_answer_delay_time = models.IntegerField(default=10)
    enabled = models.BooleanField(default=True)
    description = models.TextField(blank=True, default='')
    insert_date = models.DateTimeField(auto_now_add=True, null=True)
    insert_user = models.UUIDField(null=True, blank=True)
    update_date = models.DateTimeField(auto_now=True, null=True)
    update_user = models.UUIDField(null=True, blank=True)

    class Meta:
        db_table = 'v_call_center_agents'
        unique_together = [('domain', 'agent_name')]

    def __str__(self):
        return self.agent_name


class CallCenterTier(models.Model):
    tier_uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    domain = models.ForeignKey(Domain, on_delete=models.CASCADE, null=True, db_column='domain_uuid')
    call_center = models.ForeignKey(CallCenter, on_delete=models.CASCADE,
                                    db_column='queue_uuid', related_name='tiers')
    agent = models.ForeignKey(CallCenterAgent, on_delete=models.CASCADE,
                              db_column='agent_uuid', related_name='tiers')
    tier_agent = models.CharField(max_length=128, blank=True, default='')
    tier_level = models.IntegerField(default=1)
    tier_position = models.IntegerField(default=1)

    class Meta:
        db_table = 'v_call_center_tiers'
        unique_together = [('call_center', 'agent')]
""")

write(f"{APP}/serializers.py", """from rest_framework import serializers
from .models import CallCenter, CallCenterAgent, CallCenterTier


class CallCenterTierSerializer(serializers.ModelSerializer):
    class Meta:
        model = CallCenterTier
        fields = '__all__'
        read_only_fields = ['tier_uuid']


class CallCenterSerializer(serializers.ModelSerializer):
    tiers = CallCenterTierSerializer(many=True, read_only=True)
    domain_name = serializers.CharField(source='domain.domain_name', read_only=True)

    class Meta:
        model = CallCenter
        fields = '__all__'
        read_only_fields = ['queue_uuid', 'insert_date', 'update_date']


class CallCenterAgentSerializer(serializers.ModelSerializer):
    domain_name = serializers.CharField(source='domain.domain_name', read_only=True)

    class Meta:
        model = CallCenterAgent
        fields = '__all__'
        read_only_fields = ['agent_uuid', 'insert_date', 'update_date']
""")

write(f"{APP}/views.py", """from rest_framework import viewsets, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter
from .models import CallCenter, CallCenterAgent, CallCenterTier
from .serializers import CallCenterSerializer, CallCenterAgentSerializer, CallCenterTierSerializer


class CallCenterViewSet(viewsets.ModelViewSet):
    serializer_class = CallCenterSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ['enabled', 'strategy']
    search_fields = ['queue_name', 'description']

    def get_queryset(self):
        qs = CallCenter.objects.select_related('domain').prefetch_related('tiers')
        if hasattr(self.request, 'domain') and self.request.domain:
            return qs.filter(domain=self.request.domain)
        if not self.request.user.is_superuser:
            return qs.filter(domain=self.request.user.domain)
        return qs

    def perform_create(self, serializer):
        domain = getattr(self.request, 'domain', None) or self.request.user.domain
        serializer.save(domain=domain, insert_user=self.request.user.user_uuid)

    @action(detail=True, methods=['get'])
    def status(self, request, pk=None):
        queue = self.get_object()
        try:
            from esl.client import get_esl_client
            esl = get_esl_client()
            result = esl.callcenter_config(f'queue list members {queue.queue_name}')
            return Response({'queue': queue.queue_name, 'status': result})
        except Exception as e:
            return Response({'error': str(e)}, status=503)


class CallCenterAgentViewSet(viewsets.ModelViewSet):
    serializer_class = CallCenterAgentSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ['enabled', 'agent_type', 'agent_status']
    search_fields = ['agent_name', 'agent_contact']

    def get_queryset(self):
        qs = CallCenterAgent.objects.select_related('domain')
        if hasattr(self.request, 'domain') and self.request.domain:
            return qs.filter(domain=self.request.domain)
        if not self.request.user.is_superuser:
            return qs.filter(domain=self.request.user.domain)
        return qs

    def perform_create(self, serializer):
        domain = getattr(self.request, 'domain', None) or self.request.user.domain
        serializer.save(domain=domain, insert_user=self.request.user.user_uuid)


class CallCenterTierViewSet(viewsets.ModelViewSet):
    queryset = CallCenterTier.objects.select_related('call_center', 'agent')
    serializer_class = CallCenterTierSerializer
    permission_classes = [permissions.IsAuthenticated]
""")

write(f"{APP}/urls.py", """from rest_framework.routers import DefaultRouter
from .views import CallCenterViewSet, CallCenterAgentViewSet, CallCenterTierViewSet

router = DefaultRouter()
router.register(r'agents', CallCenterAgentViewSet, basename='call-center-agent')
router.register(r'tiers', CallCenterTierViewSet, basename='call-center-tier')
router.register(r'', CallCenterViewSet, basename='call-center')
urlpatterns = router.urls
""")

write(f"{APP}/admin.py", """from django.contrib import admin
from .models import CallCenter, CallCenterAgent, CallCenterTier

class CallCenterTierInline(admin.TabularInline):
    model = CallCenterTier
    extra = 0

@admin.register(CallCenter)
class CallCenterAdmin(admin.ModelAdmin):
    list_display = ['queue_name', 'domain', 'strategy', 'enabled']
    list_filter = ['enabled', 'strategy', 'domain']
    search_fields = ['queue_name']
    inlines = [CallCenterTierInline]

@admin.register(CallCenterAgent)
class CallCenterAgentAdmin(admin.ModelAdmin):
    list_display = ['agent_name', 'domain', 'agent_type', 'agent_status', 'enabled']
    list_filter = ['enabled', 'agent_type', 'agent_status', 'domain']
    search_fields = ['agent_name', 'agent_contact']
""")


# ─────────────────────────────────────────────────────────────────────────────
# CONFERENCES
# ─────────────────────────────────────────────────────────────────────────────
print("conferences...")
APP = make_app("conferences")

write(f"{APP}/models.py", """import uuid
from django.db import models
from core.models import Domain


class ConferenceProfile(models.Model):
    conference_profile_uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    domain = models.ForeignKey(Domain, on_delete=models.CASCADE, null=True, blank=True,
                               db_column='domain_uuid', related_name='conference_profiles')
    conference_profile_name = models.CharField(max_length=64)
    enabled = models.BooleanField(default=True)
    description = models.TextField(blank=True, default='')
    insert_date = models.DateTimeField(auto_now_add=True, null=True)

    class Meta:
        db_table = 'v_conference_profiles'

    def __str__(self):
        return self.conference_profile_name


class ConferenceProfileSetting(models.Model):
    conference_profile_setting_uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conference_profile = models.ForeignKey(ConferenceProfile, on_delete=models.CASCADE,
                                           db_column='conference_profile_uuid', related_name='settings')
    conference_profile_setting_name = models.CharField(max_length=128)
    conference_profile_setting_value = models.TextField(blank=True, default='')
    enabled = models.BooleanField(default=True)

    class Meta:
        db_table = 'v_conference_profile_settings'


class Conference(models.Model):
    conference_uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    domain = models.ForeignKey(Domain, on_delete=models.CASCADE, db_column='domain_uuid', related_name='conferences')
    conference_name = models.CharField(max_length=128)
    conference_extension = models.CharField(max_length=32, blank=True, default='')
    conference_pin = models.CharField(max_length=16, blank=True, default='')
    conference_flags = models.CharField(max_length=256, blank=True, default='')
    conference_profile = models.ForeignKey(ConferenceProfile, on_delete=models.SET_NULL,
                                           null=True, blank=True, db_column='conference_profile_uuid')
    conference_max_members = models.IntegerField(default=0)
    conference_record = models.BooleanField(default=False)
    conference_record_file = models.CharField(max_length=512, blank=True, default='')
    conference_enabled = models.BooleanField(default=True)
    conference_description = models.TextField(blank=True, default='')
    insert_date = models.DateTimeField(auto_now_add=True, null=True)
    insert_user = models.UUIDField(null=True, blank=True)
    update_date = models.DateTimeField(auto_now=True, null=True)
    update_user = models.UUIDField(null=True, blank=True)

    class Meta:
        db_table = 'v_conferences'
        unique_together = [('domain', 'conference_name')]

    def __str__(self):
        return self.conference_name


class ConferenceCenter(models.Model):
    conference_center_uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    domain = models.ForeignKey(Domain, on_delete=models.CASCADE, db_column='domain_uuid', related_name='conference_centers')
    conference_center_name = models.CharField(max_length=128)
    conference_center_extension = models.CharField(max_length=32, blank=True, default='')
    conference_center_enabled = models.BooleanField(default=True)
    conference_center_description = models.TextField(blank=True, default='')

    class Meta:
        db_table = 'v_conference_centers'
""")

write(f"{APP}/serializers.py", """from rest_framework import serializers
from .models import Conference, ConferenceProfile, ConferenceProfileSetting, ConferenceCenter


class ConferenceProfileSettingSerializer(serializers.ModelSerializer):
    class Meta:
        model = ConferenceProfileSetting
        fields = '__all__'
        read_only_fields = ['conference_profile_setting_uuid']


class ConferenceProfileSerializer(serializers.ModelSerializer):
    settings = ConferenceProfileSettingSerializer(many=True, read_only=True)

    class Meta:
        model = ConferenceProfile
        fields = '__all__'
        read_only_fields = ['conference_profile_uuid', 'insert_date']


class ConferenceSerializer(serializers.ModelSerializer):
    domain_name = serializers.CharField(source='domain.domain_name', read_only=True)
    profile_name = serializers.CharField(source='conference_profile.conference_profile_name', read_only=True)

    class Meta:
        model = Conference
        fields = '__all__'
        read_only_fields = ['conference_uuid', 'insert_date', 'update_date']
        extra_kwargs = {'conference_pin': {'write_only': True}}


class ConferenceCenterSerializer(serializers.ModelSerializer):
    class Meta:
        model = ConferenceCenter
        fields = '__all__'
        read_only_fields = ['conference_center_uuid']
""")

write(f"{APP}/views.py", """from rest_framework import viewsets, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter
from .models import Conference, ConferenceProfile, ConferenceProfileSetting, ConferenceCenter
from .serializers import ConferenceSerializer, ConferenceProfileSerializer, ConferenceCenterSerializer


class ConferenceViewSet(viewsets.ModelViewSet):
    serializer_class = ConferenceSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ['conference_enabled', 'conference_record']
    search_fields = ['conference_name', 'conference_extension', 'conference_description']

    def get_queryset(self):
        qs = Conference.objects.select_related('domain', 'conference_profile')
        if hasattr(self.request, 'domain') and self.request.domain:
            return qs.filter(domain=self.request.domain)
        if not self.request.user.is_superuser:
            return qs.filter(domain=self.request.user.domain)
        return qs

    def perform_create(self, serializer):
        domain = getattr(self.request, 'domain', None) or self.request.user.domain
        serializer.save(domain=domain, insert_user=self.request.user.user_uuid)

    @action(detail=True, methods=['get'])
    def active(self, request, pk=None):
        conf = self.get_object()
        try:
            from esl.client import get_esl_client
            esl = get_esl_client()
            result = esl.conference_cmd(conf.conference_name, 'list')
            return Response({'conference': conf.conference_name, 'members': result})
        except Exception as e:
            return Response({'error': str(e)}, status=503)

    @action(detail=True, methods=['post'])
    def kick(self, request, pk=None):
        conf = self.get_object()
        member_id = request.data.get('member_id', 'all')
        try:
            from esl.client import get_esl_client
            esl = get_esl_client()
            result = esl.conference_cmd(conf.conference_name, f'kick {member_id}')
            return Response({'result': result})
        except Exception as e:
            return Response({'error': str(e)}, status=503)


class ConferenceProfileViewSet(viewsets.ModelViewSet):
    queryset = ConferenceProfile.objects.prefetch_related('settings')
    serializer_class = ConferenceProfileSerializer
    permission_classes = [permissions.IsAuthenticated]


class ConferenceCenterViewSet(viewsets.ModelViewSet):
    serializer_class = ConferenceCenterSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = ConferenceCenter.objects.select_related('domain')
        if hasattr(self.request, 'domain') and self.request.domain:
            return qs.filter(domain=self.request.domain)
        return qs
""")

write(f"{APP}/urls.py", """from rest_framework.routers import DefaultRouter
from .views import ConferenceViewSet, ConferenceProfileViewSet, ConferenceCenterViewSet

router = DefaultRouter()
router.register(r'profiles', ConferenceProfileViewSet, basename='conference-profile')
router.register(r'centers', ConferenceCenterViewSet, basename='conference-center')
router.register(r'', ConferenceViewSet, basename='conference')
urlpatterns = router.urls
""")

write(f"{APP}/admin.py", """from django.contrib import admin
from .models import Conference, ConferenceProfile, ConferenceProfileSetting

class ConferenceProfileSettingInline(admin.TabularInline):
    model = ConferenceProfileSetting
    extra = 0

@admin.register(ConferenceProfile)
class ConferenceProfileAdmin(admin.ModelAdmin):
    list_display = ['conference_profile_name', 'enabled']
    inlines = [ConferenceProfileSettingInline]

@admin.register(Conference)
class ConferenceAdmin(admin.ModelAdmin):
    list_display = ['conference_name', 'conference_extension', 'domain', 'conference_max_members', 'conference_enabled']
    list_filter = ['conference_enabled', 'conference_record', 'domain']
    search_fields = ['conference_name', 'conference_extension']
""")


# ─────────────────────────────────────────────────────────────────────────────
# XML CDR
# ─────────────────────────────────────────────────────────────────────────────
print("xml_cdr...")
APP = make_app("xml_cdr")

write(f"{APP}/models.py", """import uuid
from django.db import models
from core.models import Domain


class XmlCdr(models.Model):
    xml_cdr_uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    domain = models.ForeignKey(Domain, on_delete=models.SET_NULL, null=True, blank=True,
                               db_column='domain_uuid', related_name='cdr_records')
    caller_id_name = models.CharField(max_length=128, blank=True, default='')
    caller_id_number = models.CharField(max_length=32, blank=True, default='', db_index=True)
    caller_destination = models.CharField(max_length=32, blank=True, default='')
    destination_number = models.CharField(max_length=32, blank=True, default='', db_index=True)
    context = models.CharField(max_length=128, blank=True, default='')
    start_epoch = models.BigIntegerField(default=0)
    start_stamp = models.DateTimeField(null=True, blank=True, db_index=True)
    answer_epoch = models.BigIntegerField(default=0)
    answer_stamp = models.DateTimeField(null=True, blank=True)
    end_epoch = models.BigIntegerField(default=0)
    end_stamp = models.DateTimeField(null=True, blank=True)
    duration = models.IntegerField(default=0, db_index=True)
    mduration = models.IntegerField(default=0)
    billsec = models.IntegerField(default=0, db_index=True)
    billmsec = models.IntegerField(default=0)
    bridge_uuid = models.UUIDField(null=True, blank=True)
    read_codec = models.CharField(max_length=32, blank=True, default='')
    read_rate = models.CharField(max_length=8, blank=True, default='')
    write_codec = models.CharField(max_length=32, blank=True, default='')
    write_rate = models.CharField(max_length=8, blank=True, default='')
    remote_media_ip = models.CharField(max_length=64, blank=True, default='')
    network_addr = models.CharField(max_length=64, blank=True, default='')
    record_path = models.CharField(max_length=512, blank=True, default='')
    record_name = models.CharField(max_length=256, blank=True, default='')
    leg = models.CharField(max_length=8, default='a', choices=[('a','A-leg'),('b','B-leg')])
    pdd_ms = models.IntegerField(default=0)
    last_app = models.CharField(max_length=64, blank=True, default='')
    last_arg = models.CharField(max_length=256, blank=True, default='')
    cc_queue = models.CharField(max_length=256, blank=True, default='')
    cc_agent = models.CharField(max_length=256, blank=True, default='')
    waitsec = models.IntegerField(default=0)
    conference_name = models.CharField(max_length=256, blank=True, default='')
    hangup_cause = models.CharField(max_length=64, blank=True, default='', db_index=True)
    hangup_cause_q850 = models.IntegerField(default=0)
    direction = models.CharField(max_length=16, default='inbound',
        choices=[('inbound','Inbound'),('outbound','Outbound'),('local','Local')])
    missed_call = models.BooleanField(default=False)
    insert_date = models.DateTimeField(auto_now_add=True, null=True, db_index=True)

    class Meta:
        db_table = 'v_xml_cdr'
        ordering = ['-start_stamp']
        indexes = [
            models.Index(fields=['start_stamp']),
            models.Index(fields=['caller_id_number']),
            models.Index(fields=['destination_number']),
            models.Index(fields=['hangup_cause']),
        ]

    def __str__(self):
        return f'{self.caller_id_number} -> {self.destination_number} ({self.billsec}s)'
""")

write(f"{APP}/serializers.py", """from rest_framework import serializers
from .models import XmlCdr


class XmlCdrSerializer(serializers.ModelSerializer):
    domain_name = serializers.CharField(source='domain.domain_name', read_only=True)

    class Meta:
        model = XmlCdr
        fields = '__all__'
        read_only_fields = ['xml_cdr_uuid', 'insert_date']
""")

write(f"{APP}/views.py", """import csv
from django.http import HttpResponse
from django.db.models import Count, Sum, Avg, Q
from rest_framework import viewsets, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from .models import XmlCdr
from .serializers import XmlCdrSerializer


class XmlCdrViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = XmlCdrSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['direction', 'hangup_cause', 'missed_call', 'leg']
    search_fields = ['caller_id_number', 'caller_id_name', 'destination_number']
    ordering_fields = ['start_stamp', 'duration', 'billsec', 'insert_date']
    ordering = ['-start_stamp']

    def get_queryset(self):
        qs = XmlCdr.objects.select_related('domain')
        if hasattr(self.request, 'domain') and self.request.domain:
            qs = qs.filter(domain=self.request.domain)
        elif not self.request.user.is_superuser:
            qs = qs.filter(domain=self.request.user.domain)

        # Date range filtering
        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')
        if start_date:
            qs = qs.filter(start_stamp__gte=start_date)
        if end_date:
            qs = qs.filter(start_stamp__lte=end_date)
        return qs

    @action(detail=False, methods=['get'])
    def summary(self, request):
        qs = self.get_queryset()
        total = qs.count()
        answered = qs.filter(billsec__gt=0).count()
        data = qs.aggregate(
            total_duration=Sum('duration'),
            total_billsec=Sum('billsec'),
            avg_duration=Avg('duration'),
        )
        return Response({
            'total_calls': total,
            'answered_calls': answered,
            'missed_calls': total - answered,
            'answer_rate': round(answered / total * 100, 1) if total else 0,
            'total_duration': data['total_duration'] or 0,
            'total_billsec': data['total_billsec'] or 0,
            'avg_duration': round(data['avg_duration'] or 0, 1),
        })

    @action(detail=False, methods=['get'])
    def export(self, request):
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="cdr.csv"'
        w = csv.writer(response)
        w.writerow(['Start Time','Caller ID','Caller Name','Destination','Duration','Billsec',
                    'Hangup Cause','Direction','Context'])
        for cdr in self.get_queryset()[:10000]:
            w.writerow([cdr.start_stamp, cdr.caller_id_number, cdr.caller_id_name,
                        cdr.destination_number, cdr.duration, cdr.billsec,
                        cdr.hangup_cause, cdr.direction, cdr.context])
        return response
""")

write(f"{APP}/urls.py", simple_urls("XmlCdrViewSet", "cdr"))

write(f"{APP}/admin.py", """from django.contrib import admin
from .models import XmlCdr

@admin.register(XmlCdr)
class XmlCdrAdmin(admin.ModelAdmin):
    list_display = ['caller_id_number', 'destination_number', 'start_stamp', 'billsec', 'hangup_cause', 'direction']
    list_filter = ['direction', 'hangup_cause', 'missed_call', 'domain']
    search_fields = ['caller_id_number', 'caller_id_name', 'destination_number']
    readonly_fields = [f.name for f in XmlCdr._meta.get_fields() if hasattr(f, 'name')]
    date_hierarchy = 'start_stamp'

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
""")


# ─────────────────────────────────────────────────────────────────────────────
# RING GROUPS
# ─────────────────────────────────────────────────────────────────────────────
print("ring_groups...")
APP = make_app("ring_groups")

write(f"{APP}/models.py", """import uuid
from django.db import models
from core.models import Domain


class RingGroup(models.Model):
    STRATEGY_CHOICES = [
        ('simultaneous','Simultaneous'),('sequence','Sequence'),
        ('enterprise','Enterprise'),('rollover','Rollover'),
    ]
    ring_group_uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    domain = models.ForeignKey(Domain, on_delete=models.CASCADE, db_column='domain_uuid', related_name='ring_groups')
    ring_group_name = models.CharField(max_length=128)
    ring_group_extension = models.CharField(max_length=32, blank=True, default='')
    ring_group_greeting = models.CharField(max_length=256, blank=True, default='')
    ring_group_cid_name_prefix = models.CharField(max_length=64, blank=True, default='')
    ring_group_cid_number_prefix = models.CharField(max_length=16, blank=True, default='')
    ring_group_caller_id_name = models.CharField(max_length=128, blank=True, default='')
    ring_group_caller_id_number = models.CharField(max_length=32, blank=True, default='')
    ring_group_strategy = models.CharField(max_length=32, choices=STRATEGY_CHOICES, default='simultaneous')
    ring_group_call_timeout = models.IntegerField(default=30)
    ring_group_timeout_app = models.CharField(max_length=64, blank=True, default='')
    ring_group_timeout_data = models.CharField(max_length=256, blank=True, default='')
    ring_group_ringback = models.CharField(max_length=256, blank=True, default='')
    ring_group_context = models.CharField(max_length=128, default='default')
    ring_group_enabled = models.BooleanField(default=True)
    ring_group_description = models.TextField(blank=True, default='')
    insert_date = models.DateTimeField(auto_now_add=True, null=True)
    insert_user = models.UUIDField(null=True, blank=True)
    update_date = models.DateTimeField(auto_now=True, null=True)
    update_user = models.UUIDField(null=True, blank=True)

    class Meta:
        db_table = 'v_ring_groups'
        unique_together = [('domain', 'ring_group_extension')]

    def __str__(self):
        return f'{self.ring_group_name} ({self.ring_group_extension})'


class RingGroupDestination(models.Model):
    ring_group_destination_uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    domain = models.ForeignKey(Domain, on_delete=models.CASCADE, null=True, db_column='domain_uuid')
    ring_group = models.ForeignKey(RingGroup, on_delete=models.CASCADE,
                                   db_column='ring_group_uuid', related_name='destinations')
    destination_number = models.CharField(max_length=64)
    destination_delay = models.IntegerField(default=0)
    destination_timeout = models.IntegerField(default=30)
    destination_prompt = models.CharField(max_length=256, blank=True, default='')
    insert_date = models.DateTimeField(auto_now_add=True, null=True)

    class Meta:
        db_table = 'v_ring_group_destinations'
        ordering = ['destination_delay', 'destination_number']
""")

write(f"{APP}/serializers.py", """from rest_framework import serializers
from .models import RingGroup, RingGroupDestination


class RingGroupDestinationSerializer(serializers.ModelSerializer):
    class Meta:
        model = RingGroupDestination
        fields = '__all__'
        read_only_fields = ['ring_group_destination_uuid', 'insert_date']


class RingGroupSerializer(serializers.ModelSerializer):
    destinations = RingGroupDestinationSerializer(many=True, read_only=True)
    domain_name = serializers.CharField(source='domain.domain_name', read_only=True)

    class Meta:
        model = RingGroup
        fields = '__all__'
        read_only_fields = ['ring_group_uuid', 'insert_date', 'update_date']
""")

write(f"{APP}/views.py", """from rest_framework import viewsets, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter
from .models import RingGroup, RingGroupDestination
from .serializers import RingGroupSerializer, RingGroupDestinationSerializer


class RingGroupViewSet(viewsets.ModelViewSet):
    serializer_class = RingGroupSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ['ring_group_enabled', 'ring_group_strategy']
    search_fields = ['ring_group_name', 'ring_group_extension']

    def get_queryset(self):
        qs = RingGroup.objects.select_related('domain').prefetch_related('destinations')
        if hasattr(self.request, 'domain') and self.request.domain:
            return qs.filter(domain=self.request.domain)
        if not self.request.user.is_superuser:
            return qs.filter(domain=self.request.user.domain)
        return qs

    def perform_create(self, serializer):
        domain = getattr(self.request, 'domain', None) or self.request.user.domain
        serializer.save(domain=domain, insert_user=self.request.user.user_uuid)

    @action(detail=False, methods=['post'])
    def reload(self, request):
        from esl.tasks import reload_xml
        reload_xml.delay()
        return Response({'status': 'queued'})


class RingGroupDestinationViewSet(viewsets.ModelViewSet):
    queryset = RingGroupDestination.objects.select_related('ring_group')
    serializer_class = RingGroupDestinationSerializer
    permission_classes = [permissions.IsAuthenticated]
""")

write(f"{APP}/urls.py", """from rest_framework.routers import DefaultRouter
from .views import RingGroupViewSet, RingGroupDestinationViewSet

router = DefaultRouter()
router.register(r'destinations', RingGroupDestinationViewSet, basename='ring-group-destination')
router.register(r'', RingGroupViewSet, basename='ring-group')
urlpatterns = router.urls
""")

write(f"{APP}/admin.py", """from django.contrib import admin
from .models import RingGroup, RingGroupDestination

class RingGroupDestinationInline(admin.TabularInline):
    model = RingGroupDestination
    extra = 0

@admin.register(RingGroup)
class RingGroupAdmin(admin.ModelAdmin):
    list_display = ['ring_group_name', 'ring_group_extension', 'ring_group_strategy', 'ring_group_enabled']
    list_filter = ['ring_group_enabled', 'ring_group_strategy', 'domain']
    search_fields = ['ring_group_name', 'ring_group_extension']
    inlines = [RingGroupDestinationInline]
""")

print("All second-batch apps done!")
