"""Generate all cloudpbx Django app files."""
import os

BASE = "D:/cloudpbx-django/backend"


def write(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"  WROTE {os.path.basename(path)}")


def make_app(app_name):
    """Ensure app directory and migrations exist."""
    app_dir = f"{BASE}/apps/{app_name}"
    mig_dir = f"{app_dir}/migrations"
    os.makedirs(app_dir, exist_ok=True)
    os.makedirs(mig_dir, exist_ok=True)
    for p in [f"{app_dir}/__init__.py", f"{mig_dir}/__init__.py"]:
        if not os.path.exists(p):
            open(p, 'w').close()
    return app_dir


# ─────────────────────────────────────────────────────────────────────────────
# HELPER: generate a simple CRUD ViewSet URL pattern
# ─────────────────────────────────────────────────────────────────────────────
def simple_urls(viewset_name, basename):
    return f"""from rest_framework.routers import DefaultRouter
from .views import {viewset_name}

router = DefaultRouter()
router.register(r'', {viewset_name}, basename='{basename}')
urlpatterns = router.urls
"""


def simple_admin(model_name, list_display, search_fields=None, list_filter=None):
    ld = ', '.join(f"'{f}'" for f in list_display)
    sf = ', '.join(f"'{f}'" for f in (search_fields or [list_display[0]]))
    lf = ', '.join(f"'{f}'" for f in (list_filter or []))
    return f"""from django.contrib import admin
from .models import {model_name}

@admin.register({model_name})
class {model_name}Admin(admin.ModelAdmin):
    list_display = [{ld}]
    search_fields = [{sf}]
    list_filter = [{lf}]
"""


# ─────────────────────────────────────────────────────────────────────────────
# EXTENSIONS
# ─────────────────────────────────────────────────────────────────────────────
print("extensions...")
APP = make_app("extensions")

write(f"{APP}/models.py", """import uuid
from django.db import models
from core.models import Domain, User


class Extension(models.Model):
    extension_uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    domain = models.ForeignKey(Domain, on_delete=models.CASCADE, db_column='domain_uuid', related_name='extensions')
    extension = models.CharField(max_length=32)
    number_alias = models.CharField(max_length=32, blank=True, default='')
    password = models.CharField(max_length=128, blank=True, default='')
    accountcode = models.CharField(max_length=32, blank=True, default='')
    effective_caller_id_name = models.CharField(max_length=128, blank=True, default='')
    effective_caller_id_number = models.CharField(max_length=32, blank=True, default='')
    outbound_caller_id_name = models.CharField(max_length=128, blank=True, default='')
    outbound_caller_id_number = models.CharField(max_length=32, blank=True, default='')
    emergency_caller_id_name = models.CharField(max_length=128, blank=True, default='')
    emergency_caller_id_number = models.CharField(max_length=32, blank=True, default='')
    directory_full_name = models.CharField(max_length=256, blank=True, default='')
    directory_visible = models.BooleanField(default=True)
    directory_exten_visible = models.BooleanField(default=True)
    limit_max = models.IntegerField(default=5)
    limit_destination = models.CharField(max_length=256, blank=True, default='')
    call_timeout = models.IntegerField(default=30)
    call_group = models.CharField(max_length=32, blank=True, default='')
    call_screen_enabled = models.BooleanField(default=False)
    user_record = models.CharField(max_length=32, blank=True, default='',
        choices=[('','Disabled'),('all','All'),('local','Local'),('outbound','Outbound'),('inbound','Inbound')])
    voicemail_enabled = models.BooleanField(default=True)
    voicemail_id = models.CharField(max_length=32, blank=True, default='')
    voicemail_password = models.CharField(max_length=32, blank=True, default='')
    voicemail_mail_to = models.EmailField(blank=True, default='')
    voicemail_file = models.CharField(max_length=32, default='attach',
        choices=[('attach','Attach'),('link','Link'),('none','None')])
    voicemail_local_after_email = models.BooleanField(default=True)
    forward_all_enabled = models.BooleanField(default=False)
    forward_all_destination = models.CharField(max_length=32, blank=True, default='')
    forward_busy_enabled = models.BooleanField(default=False)
    forward_busy_destination = models.CharField(max_length=32, blank=True, default='')
    forward_no_answer_enabled = models.BooleanField(default=False)
    forward_no_answer_destination = models.CharField(max_length=32, blank=True, default='')
    forward_user_not_registered_enabled = models.BooleanField(default=False)
    forward_user_not_registered_destination = models.CharField(max_length=32, blank=True, default='')
    user_context = models.CharField(max_length=128, default='default')
    toll_allow = models.CharField(max_length=256, blank=True, default='')
    auth_acl = models.CharField(max_length=256, blank=True, default='')
    cidr = models.CharField(max_length=256, blank=True, default='')
    sip_force_contact = models.CharField(max_length=32, blank=True, default='')
    sip_force_expires = models.IntegerField(null=True, blank=True)
    max_registrations = models.IntegerField(default=1)
    absolute_codec_string = models.CharField(max_length=256, blank=True, default='')
    force_ping = models.BooleanField(default=False)
    sip_bypass_media = models.CharField(max_length=32, blank=True, default='')
    hold_music = models.CharField(max_length=256, blank=True, default='')
    mwi_account = models.CharField(max_length=256, blank=True, default='')
    language = models.CharField(max_length=16, blank=True, default='')
    enabled = models.BooleanField(default=True)
    description = models.TextField(blank=True, default='')
    insert_date = models.DateTimeField(auto_now_add=True, null=True)
    insert_user = models.UUIDField(null=True, blank=True)
    update_date = models.DateTimeField(auto_now=True, null=True)
    update_user = models.UUIDField(null=True, blank=True)

    class Meta:
        db_table = 'v_extensions'
        unique_together = [('domain', 'extension')]
        ordering = ['extension']

    def __str__(self):
        return f'{self.extension}@{self.domain}'


class ExtensionUser(models.Model):
    extension_user_uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    domain = models.ForeignKey(Domain, on_delete=models.CASCADE, null=True, db_column='domain_uuid')
    extension = models.ForeignKey(Extension, on_delete=models.CASCADE,
                                  db_column='extension_uuid', related_name='extension_users')
    user = models.ForeignKey(User, on_delete=models.CASCADE, db_column='user_uuid',
                             to_field='user_uuid', related_name='extension_users')
    insert_date = models.DateTimeField(auto_now_add=True, null=True)

    class Meta:
        db_table = 'v_extension_users'
        unique_together = [('extension', 'user')]
""")

write(f"{APP}/serializers.py", """from rest_framework import serializers
from .models import Extension, ExtensionUser


class ExtensionListSerializer(serializers.ModelSerializer):
    domain_name = serializers.CharField(source='domain.domain_name', read_only=True)

    class Meta:
        model = Extension
        fields = ['extension_uuid', 'extension', 'number_alias', 'effective_caller_id_name',
                  'effective_caller_id_number', 'voicemail_enabled', 'enabled', 'domain_name']


class ExtensionSerializer(serializers.ModelSerializer):
    domain_name = serializers.CharField(source='domain.domain_name', read_only=True)

    class Meta:
        model = Extension
        fields = '__all__'
        read_only_fields = ['extension_uuid', 'insert_date', 'update_date']

    def validate(self, data):
        domain = data.get('domain', getattr(self.instance, 'domain', None))
        extension = data.get('extension', getattr(self.instance, 'extension', None))
        qs = Extension.objects.filter(domain=domain, extension=extension)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError({'extension': 'Extension already exists in this domain.'})
        return data


class ExtensionUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExtensionUser
        fields = '__all__'
        read_only_fields = ['extension_user_uuid', 'insert_date']
""")

write(f"{APP}/views.py", """import csv
from django.http import HttpResponse
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from .models import Extension, ExtensionUser
from .serializers import ExtensionSerializer, ExtensionListSerializer, ExtensionUserSerializer


class ExtensionViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['enabled', 'voicemail_enabled', 'call_group', 'user_context']
    search_fields = ['extension', 'number_alias', 'effective_caller_id_name', 'effective_caller_id_number']
    ordering_fields = ['extension', 'effective_caller_id_name', 'insert_date']
    ordering = ['extension']

    def get_queryset(self):
        qs = Extension.objects.select_related('domain')
        if hasattr(self.request, 'domain') and self.request.domain:
            return qs.filter(domain=self.request.domain)
        if not self.request.user.is_superuser:
            return qs.filter(domain=self.request.user.domain)
        return qs

    def get_serializer_class(self):
        return ExtensionListSerializer if self.action == 'list' else ExtensionSerializer

    def perform_create(self, serializer):
        domain = getattr(self.request, 'domain', None) or self.request.user.domain
        serializer.save(domain=domain, insert_user=self.request.user.user_uuid)

    def perform_update(self, serializer):
        serializer.save(update_user=self.request.user.user_uuid)

    @action(detail=True, methods=['post'])
    def reload(self, request, pk=None):
        from esl.tasks import reload_xml
        reload_xml.delay()
        return Response({'status': 'queued'})

    @action(detail=False, methods=['get'])
    def export(self, request):
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="extensions.csv"'
        w = csv.writer(response)
        w.writerow(['Extension','Number Alias','Caller ID Name','Caller ID Number','Voicemail','Enabled'])
        for e in self.get_queryset():
            w.writerow([e.extension, e.number_alias, e.effective_caller_id_name,
                        e.effective_caller_id_number, e.voicemail_enabled, e.enabled])
        return response


class ExtensionUserViewSet(viewsets.ModelViewSet):
    serializer_class = ExtensionUserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = ExtensionUser.objects.select_related('extension', 'user')
        if hasattr(self.request, 'domain') and self.request.domain:
            return qs.filter(domain=self.request.domain)
        return qs
""")

write(f"{APP}/urls.py", """from rest_framework.routers import DefaultRouter
from .views import ExtensionViewSet, ExtensionUserViewSet

router = DefaultRouter()
router.register(r'users', ExtensionUserViewSet, basename='extension-user')
router.register(r'', ExtensionViewSet, basename='extension')
urlpatterns = router.urls
""")

write(f"{APP}/admin.py", """from django.contrib import admin
from .models import Extension, ExtensionUser

class ExtensionUserInline(admin.TabularInline):
    model = ExtensionUser
    extra = 0

@admin.register(Extension)
class ExtensionAdmin(admin.ModelAdmin):
    list_display = ['extension', 'domain', 'effective_caller_id_name', 'voicemail_enabled', 'enabled']
    list_filter = ['enabled', 'voicemail_enabled', 'domain']
    search_fields = ['extension', 'number_alias', 'effective_caller_id_name']
    inlines = [ExtensionUserInline]
""")


# ─────────────────────────────────────────────────────────────────────────────
# DIALPLANS
# ─────────────────────────────────────────────────────────────────────────────
print("dialplans...")
APP = make_app("dialplans")

write(f"{APP}/models.py", """import uuid
from django.db import models
from core.models import Domain


class Dialplan(models.Model):
    dialplan_uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    domain = models.ForeignKey(Domain, on_delete=models.CASCADE, null=True, blank=True,
                               db_column='domain_uuid', related_name='dialplans')
    app_uuid = models.UUIDField(null=True, blank=True)
    dialplan_context = models.CharField(max_length=128, default='default')
    dialplan_name = models.CharField(max_length=128, blank=True, default='')
    dialplan_number = models.CharField(max_length=32, blank=True, default='')
    dialplan_destination = models.BooleanField(default=False)
    dialplan_continue = models.CharField(max_length=8, blank=True, default='')
    dialplan_xml = models.TextField(blank=True, default='')
    dialplan_order = models.IntegerField(default=100)
    dialplan_enabled = models.BooleanField(default=True)
    dialplan_global = models.BooleanField(default=False)
    dialplan_description = models.TextField(blank=True, default='')
    insert_date = models.DateTimeField(auto_now_add=True, null=True)
    insert_user = models.UUIDField(null=True, blank=True)
    update_date = models.DateTimeField(auto_now=True, null=True)
    update_user = models.UUIDField(null=True, blank=True)

    class Meta:
        db_table = 'v_dialplans'
        ordering = ['dialplan_order', 'dialplan_name']

    def __str__(self):
        return f'{self.dialplan_name} ({self.dialplan_context})'


class DialplanDetail(models.Model):
    TAG_CHOICES = [('condition','Condition'),('action','Action'),('anti-action','Anti-Action')]
    dialplan_detail_uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    domain = models.ForeignKey(Domain, on_delete=models.CASCADE, null=True, blank=True, db_column='domain_uuid')
    dialplan = models.ForeignKey(Dialplan, on_delete=models.CASCADE,
                                 db_column='dialplan_uuid', related_name='details')
    dialplan_detail_tag = models.CharField(max_length=32, choices=TAG_CHOICES, default='condition')
    dialplan_detail_type = models.CharField(max_length=128, blank=True, default='')
    dialplan_detail_data = models.CharField(max_length=4096, blank=True, default='')
    dialplan_detail_break = models.CharField(max_length=32, blank=True, default='')
    dialplan_detail_inline = models.BooleanField(default=False)
    dialplan_detail_group = models.IntegerField(default=0)
    dialplan_detail_order = models.IntegerField(default=10)
    insert_date = models.DateTimeField(auto_now_add=True, null=True)

    class Meta:
        db_table = 'v_dialplan_details'
        ordering = ['dialplan_detail_group', 'dialplan_detail_order']
""")

write(f"{APP}/serializers.py", """from rest_framework import serializers
from .models import Dialplan, DialplanDetail


class DialplanDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = DialplanDetail
        fields = '__all__'
        read_only_fields = ['dialplan_detail_uuid', 'insert_date']


class DialplanSerializer(serializers.ModelSerializer):
    details = DialplanDetailSerializer(many=True, read_only=True)
    domain_name = serializers.CharField(source='domain.domain_name', read_only=True)

    class Meta:
        model = Dialplan
        fields = '__all__'
        read_only_fields = ['dialplan_uuid', 'insert_date', 'update_date']


class DialplanListSerializer(serializers.ModelSerializer):
    domain_name = serializers.CharField(source='domain.domain_name', read_only=True)

    class Meta:
        model = Dialplan
        fields = ['dialplan_uuid', 'dialplan_name', 'dialplan_number', 'dialplan_context',
                  'dialplan_order', 'dialplan_enabled', 'dialplan_global', 'domain_name']
""")

write(f"{APP}/views.py", """from rest_framework import viewsets, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from .models import Dialplan, DialplanDetail
from .serializers import DialplanSerializer, DialplanListSerializer, DialplanDetailSerializer


class DialplanViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['dialplan_enabled', 'dialplan_context', 'dialplan_global', 'dialplan_destination']
    search_fields = ['dialplan_name', 'dialplan_number', 'dialplan_description']
    ordering_fields = ['dialplan_order', 'dialplan_name']

    def get_queryset(self):
        qs = Dialplan.objects.select_related('domain').prefetch_related('details')
        if hasattr(self.request, 'domain') and self.request.domain:
            return qs.filter(domain=self.request.domain)
        if not self.request.user.is_superuser:
            return qs.filter(domain=self.request.user.domain)
        return qs

    def get_serializer_class(self):
        return DialplanListSerializer if self.action == 'list' else DialplanSerializer

    def perform_create(self, serializer):
        domain = getattr(self.request, 'domain', None) or self.request.user.domain
        serializer.save(domain=domain, insert_user=self.request.user.user_uuid)

    @action(detail=False, methods=['post'])
    def reload(self, request):
        from esl.tasks import reload_xml
        reload_xml.delay()
        return Response({'status': 'queued', 'message': 'XML reload queued'})

    @action(detail=False, methods=['get'])
    def inbound(self, request):
        qs = self.get_queryset().filter(dialplan_destination=True)
        serializer = DialplanListSerializer(qs, many=True)
        return Response(serializer.data)


class DialplanDetailViewSet(viewsets.ModelViewSet):
    serializer_class = DialplanDetailSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = DialplanDetail.objects.select_related('dialplan')
        dialplan_uuid = self.request.query_params.get('dialplan')
        if dialplan_uuid:
            qs = qs.filter(dialplan__dialplan_uuid=dialplan_uuid)
        return qs
""")

write(f"{APP}/urls.py", """from rest_framework.routers import DefaultRouter
from .views import DialplanViewSet, DialplanDetailViewSet

router = DefaultRouter()
router.register(r'details', DialplanDetailViewSet, basename='dialplan-detail')
router.register(r'', DialplanViewSet, basename='dialplan')
urlpatterns = router.urls
""")

write(f"{APP}/admin.py", """from django.contrib import admin
from .models import Dialplan, DialplanDetail

class DialplanDetailInline(admin.TabularInline):
    model = DialplanDetail
    extra = 0

@admin.register(Dialplan)
class DialplanAdmin(admin.ModelAdmin):
    list_display = ['dialplan_name', 'dialplan_number', 'dialplan_context', 'dialplan_order', 'dialplan_enabled']
    list_filter = ['dialplan_enabled', 'dialplan_global', 'dialplan_context']
    search_fields = ['dialplan_name', 'dialplan_number']
    inlines = [DialplanDetailInline]
""")


# ─────────────────────────────────────────────────────────────────────────────
# VOICEMAILS
# ─────────────────────────────────────────────────────────────────────────────
print("voicemails...")
APP = make_app("voicemails")

write(f"{APP}/models.py", """import uuid
from django.db import models
from core.models import Domain


class Voicemail(models.Model):
    voicemail_uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    domain = models.ForeignKey(Domain, on_delete=models.CASCADE, db_column='domain_uuid', related_name='voicemails')
    voicemail_id = models.CharField(max_length=32)
    voicemail_password = models.CharField(max_length=32, blank=True, default='')
    voicemail_mail_to = models.EmailField(blank=True, default='')
    voicemail_sms_to = models.CharField(max_length=32, blank=True, default='')
    voicemail_transcription_enabled = models.BooleanField(default=False)
    voicemail_file = models.CharField(max_length=32, default='attach',
        choices=[('attach','Attach'),('link','Link'),('none','None')])
    voicemail_local_after_email = models.BooleanField(default=True)
    voicemail_enabled = models.BooleanField(default=True)
    voicemail_description = models.TextField(blank=True, default='')
    insert_date = models.DateTimeField(auto_now_add=True, null=True)
    insert_user = models.UUIDField(null=True, blank=True)
    update_date = models.DateTimeField(auto_now=True, null=True)
    update_user = models.UUIDField(null=True, blank=True)

    class Meta:
        db_table = 'v_voicemails'
        unique_together = [('domain', 'voicemail_id')]

    def __str__(self):
        return f'{self.voicemail_id}@{self.domain}'


class VoicemailMessage(models.Model):
    STATUS_CHOICES = [('new','New'),('saved','Saved'),('deleted','Deleted')]
    voicemail_message_uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    domain = models.ForeignKey(Domain, on_delete=models.CASCADE, null=True, db_column='domain_uuid')
    voicemail = models.ForeignKey(Voicemail, on_delete=models.CASCADE,
                                  db_column='voicemail_uuid', related_name='messages')
    created_epoch = models.BigIntegerField(default=0)
    read_epoch = models.BigIntegerField(default=0)
    caller_id_name = models.CharField(max_length=128, blank=True, default='')
    caller_id_number = models.CharField(max_length=32, blank=True, default='')
    message_num = models.IntegerField(default=0)
    message_filename = models.CharField(max_length=512, blank=True, default='')
    message_length = models.IntegerField(default=0)
    message_status = models.CharField(max_length=32, choices=STATUS_CHOICES, default='new')
    message_priority = models.CharField(max_length=16, default='normal')

    class Meta:
        db_table = 'v_voicemail_messages'
        ordering = ['-created_epoch']


class VoicemailDestination(models.Model):
    voicemail_destination_uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    domain = models.ForeignKey(Domain, on_delete=models.CASCADE, null=True, db_column='domain_uuid')
    voicemail = models.ForeignKey(Voicemail, on_delete=models.CASCADE,
                                  db_column='voicemail_uuid', related_name='destinations')
    voicemail_destination_uuid2 = models.UUIDField(null=True, blank=True)

    class Meta:
        db_table = 'v_voicemail_destinations'


class VoicemailOption(models.Model):
    voicemail_option_uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    domain = models.ForeignKey(Domain, on_delete=models.CASCADE, null=True, db_column='domain_uuid')
    voicemail = models.ForeignKey(Voicemail, on_delete=models.CASCADE,
                                  db_column='voicemail_uuid', related_name='options')
    voicemail_option_digits = models.CharField(max_length=8, blank=True, default='')
    voicemail_option_action = models.CharField(max_length=256, blank=True, default='')
    voicemail_option_param = models.CharField(max_length=256, blank=True, default='')
    voicemail_option_order = models.IntegerField(default=10)

    class Meta:
        db_table = 'v_voicemail_options'
        ordering = ['voicemail_option_order']
""")

write(f"{APP}/serializers.py", """from rest_framework import serializers
from .models import Voicemail, VoicemailMessage, VoicemailDestination, VoicemailOption


class VoicemailMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = VoicemailMessage
        fields = '__all__'
        read_only_fields = ['voicemail_message_uuid']


class VoicemailOptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = VoicemailOption
        fields = '__all__'
        read_only_fields = ['voicemail_option_uuid']


class VoicemailSerializer(serializers.ModelSerializer):
    messages = VoicemailMessageSerializer(many=True, read_only=True)
    options = VoicemailOptionSerializer(many=True, read_only=True)
    message_count = serializers.SerializerMethodField()
    new_message_count = serializers.SerializerMethodField()
    domain_name = serializers.CharField(source='domain.domain_name', read_only=True)

    class Meta:
        model = Voicemail
        fields = '__all__'
        read_only_fields = ['voicemail_uuid', 'insert_date', 'update_date']

    def get_message_count(self, obj):
        return obj.messages.exclude(message_status='deleted').count()

    def get_new_message_count(self, obj):
        return obj.messages.filter(message_status='new').count()
""")

write(f"{APP}/views.py", """from rest_framework import viewsets, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter
from .models import Voicemail, VoicemailMessage
from .serializers import VoicemailSerializer, VoicemailMessageSerializer


class VoicemailViewSet(viewsets.ModelViewSet):
    serializer_class = VoicemailSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ['voicemail_enabled']
    search_fields = ['voicemail_id', 'voicemail_mail_to', 'voicemail_description']

    def get_queryset(self):
        qs = Voicemail.objects.select_related('domain').prefetch_related('messages', 'options')
        if hasattr(self.request, 'domain') and self.request.domain:
            return qs.filter(domain=self.request.domain)
        if not self.request.user.is_superuser:
            return qs.filter(domain=self.request.user.domain)
        return qs

    def perform_create(self, serializer):
        domain = getattr(self.request, 'domain', None) or self.request.user.domain
        serializer.save(domain=domain, insert_user=self.request.user.user_uuid)

    @action(detail=True, methods=['get'])
    def messages(self, request, pk=None):
        vm = self.get_object()
        msgs = vm.messages.exclude(message_status='deleted')
        return Response(VoicemailMessageSerializer(msgs, many=True).data)

    @action(detail=True, methods=['delete'], url_path='messages/(?P<msg_uuid>[^/.]+)')
    def delete_message(self, request, pk=None, msg_uuid=None):
        vm = self.get_object()
        try:
            msg = vm.messages.get(voicemail_message_uuid=msg_uuid)
            msg.message_status = 'deleted'
            msg.save()
            return Response({'status': 'deleted'})
        except VoicemailMessage.DoesNotExist:
            from rest_framework.exceptions import NotFound
            raise NotFound('Message not found')
""")

write(f"{APP}/urls.py", """from rest_framework.routers import DefaultRouter
from .views import VoicemailViewSet

router = DefaultRouter()
router.register(r'', VoicemailViewSet, basename='voicemail')
urlpatterns = router.urls
""")

write(f"{APP}/admin.py", """from django.contrib import admin
from .models import Voicemail, VoicemailMessage

class VoicemailMessageInline(admin.TabularInline):
    model = VoicemailMessage
    extra = 0
    readonly_fields = ['created_epoch', 'caller_id_number', 'message_length', 'message_status']

@admin.register(Voicemail)
class VoicemailAdmin(admin.ModelAdmin):
    list_display = ['voicemail_id', 'domain', 'voicemail_mail_to', 'voicemail_enabled']
    list_filter = ['voicemail_enabled', 'domain']
    search_fields = ['voicemail_id', 'voicemail_mail_to']
    inlines = [VoicemailMessageInline]
""")


# ─────────────────────────────────────────────────────────────────────────────
# GATEWAYS
# ─────────────────────────────────────────────────────────────────────────────
print("gateways...")
APP = make_app("gateways")

write(f"{APP}/models.py", """import uuid
from django.db import models
from core.models import Domain


class Gateway(models.Model):
    gateway_uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    domain = models.ForeignKey(Domain, on_delete=models.CASCADE, null=True, blank=True,
                               db_column='domain_uuid', related_name='gateways')
    gateway = models.CharField(max_length=128)
    username = models.CharField(max_length=128, blank=True, default='')
    password = models.CharField(max_length=128, blank=True, default='')
    distinct_to = models.BooleanField(default=False)
    auth_username = models.CharField(max_length=128, blank=True, default='')
    realm = models.CharField(max_length=256, blank=True, default='')
    from_user = models.CharField(max_length=128, blank=True, default='')
    from_domain = models.CharField(max_length=256, blank=True, default='')
    proxy = models.CharField(max_length=256, blank=True, default='')
    register_proxy = models.CharField(max_length=256, blank=True, default='')
    outbound_proxy = models.CharField(max_length=256, blank=True, default='')
    expire_seconds = models.IntegerField(default=3600)
    register = models.BooleanField(default=True)
    register_transport = models.CharField(max_length=8, default='udp',
        choices=[('udp','UDP'),('tcp','TCP'),('tls','TLS')])
    retry_seconds = models.IntegerField(default=30)
    extension = models.CharField(max_length=32, default='auto_to_user')
    ping = models.CharField(max_length=64, blank=True, default='')
    ping_max = models.IntegerField(default=3)
    ping_min = models.IntegerField(default=1)
    caller_id_in_from = models.BooleanField(default=False)
    codec_prefs = models.CharField(max_length=128, default='PCMU,PCMA')
    inbound_codec_prefs = models.CharField(max_length=128, default='PCMU,PCMA')
    outbound_codec_prefs = models.CharField(max_length=128, default='PCMU,PCMA')
    profile = models.CharField(max_length=64, default='external')
    gateway_enabled = models.BooleanField(default=True)
    gateway_description = models.TextField(blank=True, default='')
    insert_date = models.DateTimeField(auto_now_add=True, null=True)
    insert_user = models.UUIDField(null=True, blank=True)
    update_date = models.DateTimeField(auto_now=True, null=True)
    update_user = models.UUIDField(null=True, blank=True)

    class Meta:
        db_table = 'v_gateways'
        unique_together = [('domain', 'gateway')]

    def __str__(self):
        return self.gateway
""")

write(f"{APP}/serializers.py", """from rest_framework import serializers
from .models import Gateway


class GatewaySerializer(serializers.ModelSerializer):
    domain_name = serializers.CharField(source='domain.domain_name', read_only=True)

    class Meta:
        model = Gateway
        fields = '__all__'
        read_only_fields = ['gateway_uuid', 'insert_date', 'update_date']
        extra_kwargs = {'password': {'write_only': True}}
""")

write(f"{APP}/views.py", """from rest_framework import viewsets, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter
from .models import Gateway
from .serializers import GatewaySerializer


class GatewayViewSet(viewsets.ModelViewSet):
    serializer_class = GatewaySerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ['gateway_enabled', 'register', 'profile']
    search_fields = ['gateway', 'proxy', 'realm', 'gateway_description']

    def get_queryset(self):
        qs = Gateway.objects.select_related('domain')
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
        gw = self.get_object()
        try:
            from esl.client import get_esl_client
            esl = get_esl_client()
            result = esl.gateway_status(gw.gateway)
            return Response({'gateway': gw.gateway, 'status': result})
        except Exception as e:
            return Response({'error': str(e)}, status=503)

    @action(detail=False, methods=['post'])
    def reload(self, request):
        from esl.tasks import sofia_profile_reload
        sofia_profile_reload.delay()
        return Response({'status': 'queued'})
""")

write(f"{APP}/urls.py", simple_urls("GatewayViewSet", "gateway"))

write(f"{APP}/admin.py", """from django.contrib import admin
from .models import Gateway

@admin.register(Gateway)
class GatewayAdmin(admin.ModelAdmin):
    list_display = ['gateway', 'domain', 'proxy', 'register', 'gateway_enabled']
    list_filter = ['gateway_enabled', 'register', 'profile']
    search_fields = ['gateway', 'proxy', 'realm']
""")

print("All first-batch apps done!")
