#!/usr/bin/env python3
"""
gen_apps4.py - music_on_hold, fax, email_queue, number_translations,
               modules_app, pin_numbers, vars, follow_me, call_block,
               call_broadcast, fifo, emergency, event_guard, domain_limits
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

# ──────────────────────────────────────────────────────────── music_on_hold ──
print('music_on_hold...')
make_app('music_on_hold')
d = os.path.join(BASE, 'music_on_hold')

write(os.path.join(d, 'models.py'), """
    import uuid
    from django.db import models
    from core.models import Domain

    class MusicOnHold(models.Model):
        music_on_hold_uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
        domain = models.ForeignKey(Domain, on_delete=models.CASCADE, null=True, blank=True, db_column='domain_uuid')
        music_on_hold_name = models.CharField(max_length=255)
        music_on_hold_path = models.CharField(max_length=512, blank=True)
        music_on_hold_rate = models.CharField(max_length=10, default='8000')
        music_on_hold_shuffle = models.BooleanField(default=False)
        music_on_hold_channels = models.IntegerField(default=1)
        music_on_hold_interval = models.IntegerField(default=20)
        music_on_hold_timer_name = models.CharField(max_length=64, blank=True)
        music_on_hold_chime_list = models.TextField(blank=True)
        music_on_hold_chime_freq = models.IntegerField(default=0)
        music_on_hold_chime_max = models.IntegerField(default=0)
        insert_date = models.DateTimeField(auto_now_add=True)
        insert_user = models.UUIDField(null=True, blank=True)
        update_date = models.DateTimeField(auto_now=True)
        update_user = models.UUIDField(null=True, blank=True)

        class Meta:
            db_table = 'v_music_on_hold'

        def __str__(self):
            return self.music_on_hold_name
""")

write(os.path.join(d, 'serializers.py'), """
    from rest_framework import serializers
    from .models import MusicOnHold

    class MusicOnHoldSerializer(serializers.ModelSerializer):
        class Meta:
            model = MusicOnHold
            fields = '__all__'
            read_only_fields = ['music_on_hold_uuid', 'insert_date', 'insert_user', 'update_date', 'update_user']
""")

write(os.path.join(d, 'views.py'), """
    from rest_framework import viewsets, filters
    from django_filters.rest_framework import DjangoFilterBackend
    from .models import MusicOnHold
    from .serializers import MusicOnHoldSerializer

    class MusicOnHoldViewSet(viewsets.ModelViewSet):
        queryset = MusicOnHold.objects.all()
        serializer_class = MusicOnHoldSerializer
        filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
        filterset_fields = ['domain']
        search_fields = ['music_on_hold_name']
        ordering_fields = ['music_on_hold_name']

        def get_queryset(self):
            qs = super().get_queryset()
            domain = self.request.query_params.get('domain_uuid')
            if domain:
                qs = qs.filter(domain__domain_uuid=domain)
            return qs
""")

write(os.path.join(d, 'urls.py'), """
    from rest_framework.routers import DefaultRouter
    from .views import MusicOnHoldViewSet

    router = DefaultRouter()
    router.register(r'', MusicOnHoldViewSet, basename='music-on-hold')
    urlpatterns = router.urls
""")

write(os.path.join(d, 'admin.py'), """
    from django.contrib import admin
    from .models import MusicOnHold

    @admin.register(MusicOnHold)
    class MusicOnHoldAdmin(admin.ModelAdmin):
        list_display = ['music_on_hold_name', 'music_on_hold_rate', 'music_on_hold_path']
        search_fields = ['music_on_hold_name']
""")

# ───────────────────────────────────────────────────────────────────── fax ──
print('fax...')
make_app('fax')
d = os.path.join(BASE, 'fax')

write(os.path.join(d, 'models.py'), """
    import uuid
    from django.db import models
    from core.models import Domain

    class Fax(models.Model):
        fax_uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
        domain = models.ForeignKey(Domain, on_delete=models.CASCADE, null=True, blank=True, db_column='domain_uuid')
        fax_name = models.CharField(max_length=255)
        fax_extension = models.CharField(max_length=255, blank=True)
        fax_email = models.CharField(max_length=255, blank=True)
        fax_email_connection = models.CharField(max_length=255, blank=True)
        fax_caller_id_name = models.CharField(max_length=255, blank=True)
        fax_caller_id_number = models.CharField(max_length=255, blank=True)
        fax_forward_number = models.CharField(max_length=255, blank=True)
        fax_toll_allow = models.CharField(max_length=255, blank=True)
        fax_accountcode = models.CharField(max_length=255, blank=True)
        fax_enabled = models.BooleanField(default=True)
        fax_description = models.TextField(blank=True)
        insert_date = models.DateTimeField(auto_now_add=True)
        insert_user = models.UUIDField(null=True, blank=True)
        update_date = models.DateTimeField(auto_now=True)
        update_user = models.UUIDField(null=True, blank=True)

        class Meta:
            db_table = 'v_fax'

        def __str__(self):
            return self.fax_name

    class FaxFile(models.Model):
        FAX_STATUSES = [('sent', 'Sent'), ('received', 'Received'), ('pending', 'Pending'), ('failed', 'Failed')]

        fax_file_uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
        fax = models.ForeignKey(Fax, on_delete=models.CASCADE, related_name='files', db_column='fax_uuid')
        domain = models.ForeignKey(Domain, on_delete=models.CASCADE, null=True, blank=True, db_column='domain_uuid')
        fax_file_type = models.CharField(max_length=10, default='pdf')
        fax_file_name = models.CharField(max_length=512)
        fax_file_path = models.CharField(max_length=512, blank=True)
        fax_file_status = models.CharField(max_length=20, choices=FAX_STATUSES, default='pending')
        fax_file_pages = models.IntegerField(default=0)
        fax_file_duration = models.IntegerField(default=0)
        fax_file_caller_id_number = models.CharField(max_length=255, blank=True)
        fax_file_destination_number = models.CharField(max_length=255, blank=True)
        fax_file_date = models.DateTimeField(null=True, blank=True)
        insert_date = models.DateTimeField(auto_now_add=True)

        class Meta:
            db_table = 'v_fax_files'
            ordering = ['-insert_date']
""")

write(os.path.join(d, 'serializers.py'), """
    from rest_framework import serializers
    from .models import Fax, FaxFile

    class FaxFileSerializer(serializers.ModelSerializer):
        class Meta:
            model = FaxFile
            fields = '__all__'
            read_only_fields = ['fax_file_uuid', 'insert_date']

    class FaxSerializer(serializers.ModelSerializer):
        files = FaxFileSerializer(many=True, read_only=True)

        class Meta:
            model = Fax
            fields = '__all__'
            read_only_fields = ['fax_uuid', 'insert_date', 'insert_user', 'update_date', 'update_user']

    class FaxListSerializer(serializers.ModelSerializer):
        class Meta:
            model = Fax
            fields = ['fax_uuid', 'fax_name', 'fax_extension', 'fax_email', 'fax_enabled']
""")

write(os.path.join(d, 'views.py'), """
    from rest_framework import viewsets, filters
    from django_filters.rest_framework import DjangoFilterBackend
    from .models import Fax, FaxFile
    from .serializers import FaxSerializer, FaxListSerializer, FaxFileSerializer

    class FaxViewSet(viewsets.ModelViewSet):
        queryset = Fax.objects.all().prefetch_related('files')
        serializer_class = FaxSerializer
        filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
        filterset_fields = ['domain', 'fax_enabled']
        search_fields = ['fax_name', 'fax_extension', 'fax_email']
        ordering_fields = ['fax_name', 'fax_extension']

        def get_queryset(self):
            qs = super().get_queryset()
            domain = self.request.query_params.get('domain_uuid')
            if domain:
                qs = qs.filter(domain__domain_uuid=domain)
            return qs

        def get_serializer_class(self):
            if self.action == 'list':
                return FaxListSerializer
            return FaxSerializer

    class FaxFileViewSet(viewsets.ModelViewSet):
        queryset = FaxFile.objects.all()
        serializer_class = FaxFileSerializer
        filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
        filterset_fields = ['fax', 'fax_file_status']
        ordering_fields = ['fax_file_date', 'insert_date']
""")

write(os.path.join(d, 'urls.py'), """
    from rest_framework.routers import DefaultRouter
    from .views import FaxViewSet, FaxFileViewSet

    router = DefaultRouter()
    router.register(r'', FaxViewSet, basename='fax')
    router.register(r'files', FaxFileViewSet, basename='fax-file')
    urlpatterns = router.urls
""")

write(os.path.join(d, 'admin.py'), """
    from django.contrib import admin
    from .models import Fax, FaxFile

    class FaxFileInline(admin.TabularInline):
        model = FaxFile
        extra = 0
        readonly_fields = ['insert_date']

    @admin.register(Fax)
    class FaxAdmin(admin.ModelAdmin):
        list_display = ['fax_name', 'fax_extension', 'fax_email', 'fax_enabled']
        list_filter = ['fax_enabled']
        search_fields = ['fax_name', 'fax_extension']
        inlines = [FaxFileInline]
""")

# ──────────────────────────────────────────────────────────── email_queue ──
print('email_queue...')
make_app('email_queue')
d = os.path.join(BASE, 'email_queue')

write(os.path.join(d, 'models.py'), """
    import uuid
    from django.db import models
    from core.models import Domain

    class EmailQueue(models.Model):
        STATUSES = [('pending', 'Pending'), ('sent', 'Sent'), ('failed', 'Failed')]

        email_queue_uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
        domain = models.ForeignKey(Domain, on_delete=models.CASCADE, null=True, blank=True, db_column='domain_uuid')
        email_queue_from = models.EmailField(blank=True)
        email_queue_to = models.EmailField()
        email_queue_cc = models.EmailField(blank=True)
        email_queue_subject = models.CharField(max_length=512)
        email_queue_body = models.TextField()
        email_queue_status = models.CharField(max_length=20, choices=STATUSES, default='pending')
        email_queue_retry_count = models.IntegerField(default=0)
        email_queue_date = models.DateTimeField(null=True, blank=True)
        insert_date = models.DateTimeField(auto_now_add=True)
        insert_user = models.UUIDField(null=True, blank=True)

        class Meta:
            db_table = 'v_email_queue'
            ordering = ['-insert_date']

        def __str__(self):
            return f'{self.email_queue_to}: {self.email_queue_subject}'
""")

write(os.path.join(d, 'serializers.py'), """
    from rest_framework import serializers
    from .models import EmailQueue

    class EmailQueueSerializer(serializers.ModelSerializer):
        class Meta:
            model = EmailQueue
            fields = '__all__'
            read_only_fields = ['email_queue_uuid', 'insert_date', 'insert_user']
""")

write(os.path.join(d, 'views.py'), """
    from rest_framework import viewsets, filters
    from django_filters.rest_framework import DjangoFilterBackend
    from .models import EmailQueue
    from .serializers import EmailQueueSerializer

    class EmailQueueViewSet(viewsets.ModelViewSet):
        queryset = EmailQueue.objects.all()
        serializer_class = EmailQueueSerializer
        filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
        filterset_fields = ['domain', 'email_queue_status']
        search_fields = ['email_queue_to', 'email_queue_subject']
        ordering_fields = ['insert_date', 'email_queue_status']
""")

write(os.path.join(d, 'urls.py'), """
    from rest_framework.routers import DefaultRouter
    from .views import EmailQueueViewSet

    router = DefaultRouter()
    router.register(r'', EmailQueueViewSet, basename='email-queue')
    urlpatterns = router.urls
""")

write(os.path.join(d, 'admin.py'), """
    from django.contrib import admin
    from .models import EmailQueue

    @admin.register(EmailQueue)
    class EmailQueueAdmin(admin.ModelAdmin):
        list_display = ['email_queue_to', 'email_queue_subject', 'email_queue_status', 'insert_date']
        list_filter = ['email_queue_status']
        search_fields = ['email_queue_to', 'email_queue_subject']
""")

# ────────────────────────────────────────────────────── number_translations ──
print('number_translations...')
make_app('number_translations')
d = os.path.join(BASE, 'number_translations')

write(os.path.join(d, 'models.py'), """
    import uuid
    from django.db import models
    from core.models import Domain

    class NumberTranslation(models.Model):
        number_translation_uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
        domain = models.ForeignKey(Domain, on_delete=models.CASCADE, null=True, blank=True, db_column='domain_uuid')
        number_translation_name = models.CharField(max_length=255)
        number_translation_description = models.TextField(blank=True)
        insert_date = models.DateTimeField(auto_now_add=True)
        insert_user = models.UUIDField(null=True, blank=True)
        update_date = models.DateTimeField(auto_now=True)
        update_user = models.UUIDField(null=True, blank=True)

        class Meta:
            db_table = 'v_number_translations'

        def __str__(self):
            return self.number_translation_name

    class NumberTranslationDetail(models.Model):
        number_translation_detail_uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
        number_translation = models.ForeignKey(NumberTranslation, on_delete=models.CASCADE, related_name='details', db_column='number_translation_uuid')
        domain = models.ForeignKey(Domain, on_delete=models.CASCADE, null=True, blank=True, db_column='domain_uuid')
        number_translation_detail_order = models.IntegerField(default=10)
        number_translation_detail_condition_field = models.CharField(max_length=64, blank=True)
        number_translation_detail_condition_expression = models.CharField(max_length=255, blank=True)
        number_translation_detail_action_expression = models.CharField(max_length=255, blank=True)
        insert_date = models.DateTimeField(auto_now_add=True)

        class Meta:
            db_table = 'v_number_translation_details'
            ordering = ['number_translation_detail_order']
""")

write(os.path.join(d, 'serializers.py'), """
    from rest_framework import serializers
    from .models import NumberTranslation, NumberTranslationDetail

    class NumberTranslationDetailSerializer(serializers.ModelSerializer):
        class Meta:
            model = NumberTranslationDetail
            fields = '__all__'
            read_only_fields = ['number_translation_detail_uuid', 'insert_date']

    class NumberTranslationSerializer(serializers.ModelSerializer):
        details = NumberTranslationDetailSerializer(many=True, read_only=True)

        class Meta:
            model = NumberTranslation
            fields = '__all__'
            read_only_fields = ['number_translation_uuid', 'insert_date', 'insert_user', 'update_date', 'update_user']
""")

write(os.path.join(d, 'views.py'), """
    from rest_framework import viewsets, filters
    from django_filters.rest_framework import DjangoFilterBackend
    from .models import NumberTranslation, NumberTranslationDetail
    from .serializers import NumberTranslationSerializer, NumberTranslationDetailSerializer

    class NumberTranslationViewSet(viewsets.ModelViewSet):
        queryset = NumberTranslation.objects.all().prefetch_related('details')
        serializer_class = NumberTranslationSerializer
        filter_backends = [DjangoFilterBackend, filters.SearchFilter]
        filterset_fields = ['domain']
        search_fields = ['number_translation_name']

        def get_queryset(self):
            qs = super().get_queryset()
            domain = self.request.query_params.get('domain_uuid')
            if domain:
                qs = qs.filter(domain__domain_uuid=domain)
            return qs

    class NumberTranslationDetailViewSet(viewsets.ModelViewSet):
        queryset = NumberTranslationDetail.objects.all()
        serializer_class = NumberTranslationDetailSerializer
        filter_backends = [DjangoFilterBackend]
        filterset_fields = ['number_translation']
""")

write(os.path.join(d, 'urls.py'), """
    from rest_framework.routers import DefaultRouter
    from .views import NumberTranslationViewSet, NumberTranslationDetailViewSet

    router = DefaultRouter()
    router.register(r'', NumberTranslationViewSet, basename='number-translation')
    router.register(r'details', NumberTranslationDetailViewSet, basename='number-translation-detail')
    urlpatterns = router.urls
""")

write(os.path.join(d, 'admin.py'), """
    from django.contrib import admin
    from .models import NumberTranslation, NumberTranslationDetail

    class NumberTranslationDetailInline(admin.TabularInline):
        model = NumberTranslationDetail
        extra = 1

    @admin.register(NumberTranslation)
    class NumberTranslationAdmin(admin.ModelAdmin):
        list_display = ['number_translation_name']
        search_fields = ['number_translation_name']
        inlines = [NumberTranslationDetailInline]
""")

# ───────────────────────────────────────────────────────────── pin_numbers ──
print('pin_numbers...')
make_app('pin_numbers')
d = os.path.join(BASE, 'pin_numbers')

write(os.path.join(d, 'models.py'), """
    import uuid
    from django.db import models
    from core.models import Domain

    class PinNumber(models.Model):
        pin_number_uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
        domain = models.ForeignKey(Domain, on_delete=models.CASCADE, null=True, blank=True, db_column='domain_uuid')
        pin_number = models.CharField(max_length=64)
        pin_number_limit = models.CharField(max_length=64, blank=True)
        pin_number_toll_allow = models.CharField(max_length=255, blank=True)
        pin_number_accountcode = models.CharField(max_length=255, blank=True)
        pin_number_enabled = models.BooleanField(default=True)
        pin_number_description = models.TextField(blank=True)
        insert_date = models.DateTimeField(auto_now_add=True)
        insert_user = models.UUIDField(null=True, blank=True)
        update_date = models.DateTimeField(auto_now=True)
        update_user = models.UUIDField(null=True, blank=True)

        class Meta:
            db_table = 'v_pin_numbers'

        def __str__(self):
            return self.pin_number
""")

write(os.path.join(d, 'serializers.py'), """
    from rest_framework import serializers
    from .models import PinNumber

    class PinNumberSerializer(serializers.ModelSerializer):
        class Meta:
            model = PinNumber
            fields = '__all__'
            read_only_fields = ['pin_number_uuid', 'insert_date', 'insert_user', 'update_date', 'update_user']
            extra_kwargs = {'pin_number': {'write_only': True}}
""")

write(os.path.join(d, 'views.py'), """
    from rest_framework import viewsets, filters
    from django_filters.rest_framework import DjangoFilterBackend
    from .models import PinNumber
    from .serializers import PinNumberSerializer

    class PinNumberViewSet(viewsets.ModelViewSet):
        queryset = PinNumber.objects.all()
        serializer_class = PinNumberSerializer
        filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
        filterset_fields = ['domain', 'pin_number_enabled']
        ordering_fields = ['insert_date']

        def get_queryset(self):
            qs = super().get_queryset()
            domain = self.request.query_params.get('domain_uuid')
            if domain:
                qs = qs.filter(domain__domain_uuid=domain)
            return qs
""")

write(os.path.join(d, 'urls.py'), """
    from rest_framework.routers import DefaultRouter
    from .views import PinNumberViewSet

    router = DefaultRouter()
    router.register(r'', PinNumberViewSet, basename='pin-number')
    urlpatterns = router.urls
""")

write(os.path.join(d, 'admin.py'), """
    from django.contrib import admin
    from .models import PinNumber

    @admin.register(PinNumber)
    class PinNumberAdmin(admin.ModelAdmin):
        list_display = ['pin_number_enabled', 'pin_number_accountcode', 'insert_date']
        list_filter = ['pin_number_enabled']
""")

# ──────────────────────────────────────────────────────────────────── vars ──
print('vars...')
make_app('vars')
d = os.path.join(BASE, 'vars')

write(os.path.join(d, 'models.py'), """
    import uuid
    from django.db import models
    from core.models import Domain

    class Variable(models.Model):
        variable_uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
        domain = models.ForeignKey(Domain, on_delete=models.CASCADE, null=True, blank=True, db_column='domain_uuid')
        variable_name = models.CharField(max_length=255)
        variable_value = models.TextField(blank=True)
        variable_enabled = models.BooleanField(default=True)
        variable_description = models.TextField(blank=True)
        insert_date = models.DateTimeField(auto_now_add=True)
        insert_user = models.UUIDField(null=True, blank=True)
        update_date = models.DateTimeField(auto_now=True)
        update_user = models.UUIDField(null=True, blank=True)

        class Meta:
            db_table = 'v_variables'

        def __str__(self):
            return self.variable_name
""")

write(os.path.join(d, 'serializers.py'), """
    from rest_framework import serializers
    from .models import Variable

    class VariableSerializer(serializers.ModelSerializer):
        class Meta:
            model = Variable
            fields = '__all__'
            read_only_fields = ['variable_uuid', 'insert_date', 'insert_user', 'update_date', 'update_user']
""")

write(os.path.join(d, 'views.py'), """
    from rest_framework import viewsets, filters
    from django_filters.rest_framework import DjangoFilterBackend
    from .models import Variable
    from .serializers import VariableSerializer

    class VariableViewSet(viewsets.ModelViewSet):
        queryset = Variable.objects.all()
        serializer_class = VariableSerializer
        filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
        filterset_fields = ['domain', 'variable_enabled']
        search_fields = ['variable_name']
        ordering_fields = ['variable_name']

        def get_queryset(self):
            qs = super().get_queryset()
            domain = self.request.query_params.get('domain_uuid')
            if domain:
                qs = qs.filter(domain__domain_uuid=domain)
            return qs
""")

write(os.path.join(d, 'urls.py'), """
    from rest_framework.routers import DefaultRouter
    from .views import VariableViewSet

    router = DefaultRouter()
    router.register(r'', VariableViewSet, basename='variable')
    urlpatterns = router.urls
""")

write(os.path.join(d, 'admin.py'), """
    from django.contrib import admin
    from .models import Variable

    @admin.register(Variable)
    class VariableAdmin(admin.ModelAdmin):
        list_display = ['variable_name', 'variable_value', 'variable_enabled']
        list_filter = ['variable_enabled']
        search_fields = ['variable_name']
""")

# ───────────────────────────────────────────────────────────── follow_me ──
print('follow_me...')
make_app('follow_me')
d = os.path.join(BASE, 'follow_me')

write(os.path.join(d, 'models.py'), """
    import uuid
    from django.db import models
    from core.models import Domain

    class FollowMe(models.Model):
        follow_me_uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
        domain = models.ForeignKey(Domain, on_delete=models.CASCADE, null=True, blank=True, db_column='domain_uuid')
        follow_me_name = models.CharField(max_length=255)
        follow_me_context = models.CharField(max_length=128, blank=True)
        follow_me_prompt = models.BooleanField(default=False)
        follow_me_cid_name_prefix = models.CharField(max_length=64, blank=True)
        follow_me_missed_call_email = models.CharField(max_length=255, blank=True)
        follow_me_description = models.TextField(blank=True)
        insert_date = models.DateTimeField(auto_now_add=True)
        insert_user = models.UUIDField(null=True, blank=True)
        update_date = models.DateTimeField(auto_now=True)
        update_user = models.UUIDField(null=True, blank=True)

        class Meta:
            db_table = 'v_follow_me'

        def __str__(self):
            return self.follow_me_name

    class FollowMeDestination(models.Model):
        follow_me_destination_uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
        follow_me = models.ForeignKey(FollowMe, on_delete=models.CASCADE, related_name='destinations', db_column='follow_me_uuid')
        domain = models.ForeignKey(Domain, on_delete=models.CASCADE, null=True, blank=True, db_column='domain_uuid')
        follow_me_destination_order = models.IntegerField(default=1)
        follow_me_destination = models.CharField(max_length=255)
        follow_me_delay = models.IntegerField(default=0)
        follow_me_timeout = models.IntegerField(default=30)
        follow_me_prompt = models.BooleanField(default=False)
        insert_date = models.DateTimeField(auto_now_add=True)

        class Meta:
            db_table = 'v_follow_me_destinations'
            ordering = ['follow_me_destination_order']
""")

write(os.path.join(d, 'serializers.py'), """
    from rest_framework import serializers
    from .models import FollowMe, FollowMeDestination

    class FollowMeDestinationSerializer(serializers.ModelSerializer):
        class Meta:
            model = FollowMeDestination
            fields = '__all__'
            read_only_fields = ['follow_me_destination_uuid', 'insert_date']

    class FollowMeSerializer(serializers.ModelSerializer):
        destinations = FollowMeDestinationSerializer(many=True, read_only=True)

        class Meta:
            model = FollowMe
            fields = '__all__'
            read_only_fields = ['follow_me_uuid', 'insert_date', 'insert_user', 'update_date', 'update_user']
""")

write(os.path.join(d, 'views.py'), """
    from rest_framework import viewsets, filters
    from django_filters.rest_framework import DjangoFilterBackend
    from .models import FollowMe, FollowMeDestination
    from .serializers import FollowMeSerializer, FollowMeDestinationSerializer

    class FollowMeViewSet(viewsets.ModelViewSet):
        queryset = FollowMe.objects.all().prefetch_related('destinations')
        serializer_class = FollowMeSerializer
        filter_backends = [DjangoFilterBackend, filters.SearchFilter]
        filterset_fields = ['domain']
        search_fields = ['follow_me_name']

        def get_queryset(self):
            qs = super().get_queryset()
            domain = self.request.query_params.get('domain_uuid')
            if domain:
                qs = qs.filter(domain__domain_uuid=domain)
            return qs

    class FollowMeDestinationViewSet(viewsets.ModelViewSet):
        queryset = FollowMeDestination.objects.all()
        serializer_class = FollowMeDestinationSerializer
        filter_backends = [DjangoFilterBackend]
        filterset_fields = ['follow_me']
""")

write(os.path.join(d, 'urls.py'), """
    from rest_framework.routers import DefaultRouter
    from .views import FollowMeViewSet, FollowMeDestinationViewSet

    router = DefaultRouter()
    router.register(r'', FollowMeViewSet, basename='follow-me')
    router.register(r'destinations', FollowMeDestinationViewSet, basename='follow-me-destination')
    urlpatterns = router.urls
""")

write(os.path.join(d, 'admin.py'), """
    from django.contrib import admin
    from .models import FollowMe, FollowMeDestination

    class FollowMeDestinationInline(admin.TabularInline):
        model = FollowMeDestination
        extra = 1

    @admin.register(FollowMe)
    class FollowMeAdmin(admin.ModelAdmin):
        list_display = ['follow_me_name', 'follow_me_context']
        search_fields = ['follow_me_name']
        inlines = [FollowMeDestinationInline]
""")

# ──────────────────────────────────────────────────────────── call_block ──
print('call_block...')
make_app('call_block')
d = os.path.join(BASE, 'call_block')

write(os.path.join(d, 'models.py'), """
    import uuid
    from django.db import models
    from core.models import Domain

    class CallBlock(models.Model):
        ACTIONS = [('block', 'Block'), ('allow', 'Allow')]

        call_block_uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
        domain = models.ForeignKey(Domain, on_delete=models.CASCADE, null=True, blank=True, db_column='domain_uuid')
        call_block_number = models.CharField(max_length=255)
        call_block_action = models.CharField(max_length=10, choices=ACTIONS, default='block')
        call_block_enabled = models.BooleanField(default=True)
        call_block_description = models.TextField(blank=True)
        insert_date = models.DateTimeField(auto_now_add=True)
        insert_user = models.UUIDField(null=True, blank=True)
        update_date = models.DateTimeField(auto_now=True)
        update_user = models.UUIDField(null=True, blank=True)

        class Meta:
            db_table = 'v_call_block'

        def __str__(self):
            return f'{self.call_block_number} ({self.call_block_action})'
""")

write(os.path.join(d, 'serializers.py'), """
    from rest_framework import serializers
    from .models import CallBlock

    class CallBlockSerializer(serializers.ModelSerializer):
        class Meta:
            model = CallBlock
            fields = '__all__'
            read_only_fields = ['call_block_uuid', 'insert_date', 'insert_user', 'update_date', 'update_user']
""")

write(os.path.join(d, 'views.py'), """
    from rest_framework import viewsets, filters
    from django_filters.rest_framework import DjangoFilterBackend
    from .models import CallBlock
    from .serializers import CallBlockSerializer

    class CallBlockViewSet(viewsets.ModelViewSet):
        queryset = CallBlock.objects.all()
        serializer_class = CallBlockSerializer
        filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
        filterset_fields = ['domain', 'call_block_action', 'call_block_enabled']
        search_fields = ['call_block_number']
        ordering_fields = ['call_block_number', 'insert_date']

        def get_queryset(self):
            qs = super().get_queryset()
            domain = self.request.query_params.get('domain_uuid')
            if domain:
                qs = qs.filter(domain__domain_uuid=domain)
            return qs
""")

write(os.path.join(d, 'urls.py'), """
    from rest_framework.routers import DefaultRouter
    from .views import CallBlockViewSet

    router = DefaultRouter()
    router.register(r'', CallBlockViewSet, basename='call-block')
    urlpatterns = router.urls
""")

write(os.path.join(d, 'admin.py'), """
    from django.contrib import admin
    from .models import CallBlock

    @admin.register(CallBlock)
    class CallBlockAdmin(admin.ModelAdmin):
        list_display = ['call_block_number', 'call_block_action', 'call_block_enabled']
        list_filter = ['call_block_action', 'call_block_enabled']
        search_fields = ['call_block_number']
""")

# ─────────────────────────────────────────────────────── call_broadcast ──
print('call_broadcast...')
make_app('call_broadcast')
d = os.path.join(BASE, 'call_broadcast')

write(os.path.join(d, 'models.py'), """
    import uuid
    from django.db import models
    from core.models import Domain

    class CallBroadcast(models.Model):
        call_broadcast_uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
        domain = models.ForeignKey(Domain, on_delete=models.CASCADE, null=True, blank=True, db_column='domain_uuid')
        call_broadcast_name = models.CharField(max_length=255)
        call_broadcast_caller_id_name = models.CharField(max_length=255, blank=True)
        call_broadcast_caller_id_number = models.CharField(max_length=255, blank=True)
        call_broadcast_timeout = models.IntegerField(default=60)
        call_broadcast_context = models.CharField(max_length=128, blank=True)
        call_broadcast_recording = models.CharField(max_length=512, blank=True)
        call_broadcast_enabled = models.BooleanField(default=True)
        call_broadcast_description = models.TextField(blank=True)
        insert_date = models.DateTimeField(auto_now_add=True)
        insert_user = models.UUIDField(null=True, blank=True)
        update_date = models.DateTimeField(auto_now=True)
        update_user = models.UUIDField(null=True, blank=True)

        class Meta:
            db_table = 'v_call_broadcast'

        def __str__(self):
            return self.call_broadcast_name

    class CallBroadcastContact(models.Model):
        call_broadcast_contact_uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
        call_broadcast = models.ForeignKey(CallBroadcast, on_delete=models.CASCADE, related_name='contacts', db_column='call_broadcast_uuid')
        domain = models.ForeignKey(Domain, on_delete=models.CASCADE, null=True, blank=True, db_column='domain_uuid')
        call_broadcast_contact_number = models.CharField(max_length=255)
        call_broadcast_contact_status = models.CharField(max_length=20, default='pending')
        insert_date = models.DateTimeField(auto_now_add=True)

        class Meta:
            db_table = 'v_call_broadcast_contacts'
""")

write(os.path.join(d, 'serializers.py'), """
    from rest_framework import serializers
    from .models import CallBroadcast, CallBroadcastContact

    class CallBroadcastContactSerializer(serializers.ModelSerializer):
        class Meta:
            model = CallBroadcastContact
            fields = '__all__'
            read_only_fields = ['call_broadcast_contact_uuid', 'insert_date']

    class CallBroadcastSerializer(serializers.ModelSerializer):
        contacts = CallBroadcastContactSerializer(many=True, read_only=True)

        class Meta:
            model = CallBroadcast
            fields = '__all__'
            read_only_fields = ['call_broadcast_uuid', 'insert_date', 'insert_user', 'update_date', 'update_user']
""")

write(os.path.join(d, 'views.py'), """
    from rest_framework import viewsets, filters, status
    from rest_framework.decorators import action
    from rest_framework.response import Response
    from django_filters.rest_framework import DjangoFilterBackend
    from .models import CallBroadcast, CallBroadcastContact
    from .serializers import CallBroadcastSerializer, CallBroadcastContactSerializer
    from esl.tasks import originate_call

    class CallBroadcastViewSet(viewsets.ModelViewSet):
        queryset = CallBroadcast.objects.all().prefetch_related('contacts')
        serializer_class = CallBroadcastSerializer
        filter_backends = [DjangoFilterBackend, filters.SearchFilter]
        filterset_fields = ['domain', 'call_broadcast_enabled']
        search_fields = ['call_broadcast_name']

        def get_queryset(self):
            qs = super().get_queryset()
            domain = self.request.query_params.get('domain_uuid')
            if domain:
                qs = qs.filter(domain__domain_uuid=domain)
            return qs

        @action(detail=True, methods=['post'])
        def start(self, request, pk=None):
            broadcast = self.get_object()
            for contact in broadcast.contacts.filter(call_broadcast_contact_status='pending'):
                originate_call.delay(
                    src=broadcast.call_broadcast_caller_id_number,
                    dst=contact.call_broadcast_contact_number,
                    recording=broadcast.call_broadcast_recording
                )
            return Response({'status': 'broadcast started', 'contacts': broadcast.contacts.count()})

    class CallBroadcastContactViewSet(viewsets.ModelViewSet):
        queryset = CallBroadcastContact.objects.all()
        serializer_class = CallBroadcastContactSerializer
        filter_backends = [DjangoFilterBackend]
        filterset_fields = ['call_broadcast', 'call_broadcast_contact_status']
""")

write(os.path.join(d, 'urls.py'), """
    from rest_framework.routers import DefaultRouter
    from .views import CallBroadcastViewSet, CallBroadcastContactViewSet

    router = DefaultRouter()
    router.register(r'', CallBroadcastViewSet, basename='call-broadcast')
    router.register(r'contacts', CallBroadcastContactViewSet, basename='call-broadcast-contact')
    urlpatterns = router.urls
""")

write(os.path.join(d, 'admin.py'), """
    from django.contrib import admin
    from .models import CallBroadcast, CallBroadcastContact

    class CallBroadcastContactInline(admin.TabularInline):
        model = CallBroadcastContact
        extra = 1

    @admin.register(CallBroadcast)
    class CallBroadcastAdmin(admin.ModelAdmin):
        list_display = ['call_broadcast_name', 'call_broadcast_caller_id_number', 'call_broadcast_enabled']
        list_filter = ['call_broadcast_enabled']
        search_fields = ['call_broadcast_name']
        inlines = [CallBroadcastContactInline]
""")

# ──────────────────────────────────────────────────────────────── fifo ──
print('fifo...')
make_app('fifo')
d = os.path.join(BASE, 'fifo')

write(os.path.join(d, 'models.py'), """
    import uuid
    from django.db import models
    from core.models import Domain

    class Fifo(models.Model):
        fifo_uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
        domain = models.ForeignKey(Domain, on_delete=models.CASCADE, null=True, blank=True, db_column='domain_uuid')
        fifo_name = models.CharField(max_length=255)
        fifo_label = models.CharField(max_length=255, blank=True)
        fifo_extension = models.CharField(max_length=255, blank=True)
        fifo_announcement = models.CharField(max_length=255, blank=True)
        fifo_music = models.CharField(max_length=255, blank=True)
        fifo_strategy = models.CharField(max_length=64, default='default')
        fifo_caller_hang_up_opt = models.CharField(max_length=10, blank=True)
        fifo_caller_exit_key = models.CharField(max_length=10, blank=True)
        fifo_max_wait_time = models.IntegerField(default=0)
        fifo_max_wait_time_with_no_agent = models.IntegerField(default=0)
        fifo_timeout_priority = models.CharField(max_length=10, blank=True)
        fifo_pop_on_lost_agent = models.CharField(max_length=10, default='true')
        fifo_enabled = models.BooleanField(default=True)
        fifo_description = models.TextField(blank=True)
        insert_date = models.DateTimeField(auto_now_add=True)
        insert_user = models.UUIDField(null=True, blank=True)
        update_date = models.DateTimeField(auto_now=True)
        update_user = models.UUIDField(null=True, blank=True)

        class Meta:
            db_table = 'v_fifo'

        def __str__(self):
            return self.fifo_name

    class FifoCallers(models.Model):
        fifo_caller_uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
        fifo = models.ForeignKey(Fifo, on_delete=models.CASCADE, related_name='callers', db_column='fifo_uuid')
        domain = models.ForeignKey(Domain, on_delete=models.CASCADE, null=True, blank=True, db_column='domain_uuid')
        fifo_caller_caller_id_name = models.CharField(max_length=255, blank=True)
        fifo_caller_caller_id_number = models.CharField(max_length=255, blank=True)
        fifo_caller_status = models.CharField(max_length=20, default='waiting')
        insert_date = models.DateTimeField(auto_now_add=True)

        class Meta:
            db_table = 'v_fifo_callers'
""")

write(os.path.join(d, 'serializers.py'), """
    from rest_framework import serializers
    from .models import Fifo, FifoCallers

    class FifoCallersSerializer(serializers.ModelSerializer):
        class Meta:
            model = FifoCallers
            fields = '__all__'
            read_only_fields = ['fifo_caller_uuid', 'insert_date']

    class FifoSerializer(serializers.ModelSerializer):
        callers = FifoCallersSerializer(many=True, read_only=True)

        class Meta:
            model = Fifo
            fields = '__all__'
            read_only_fields = ['fifo_uuid', 'insert_date', 'insert_user', 'update_date', 'update_user']

    class FifoListSerializer(serializers.ModelSerializer):
        class Meta:
            model = Fifo
            fields = ['fifo_uuid', 'fifo_name', 'fifo_extension', 'fifo_strategy', 'fifo_enabled']
""")

write(os.path.join(d, 'views.py'), """
    from rest_framework import viewsets, filters
    from django_filters.rest_framework import DjangoFilterBackend
    from .models import Fifo, FifoCallers
    from .serializers import FifoSerializer, FifoListSerializer, FifoCallersSerializer

    class FifoViewSet(viewsets.ModelViewSet):
        queryset = Fifo.objects.all().prefetch_related('callers')
        serializer_class = FifoSerializer
        filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
        filterset_fields = ['domain', 'fifo_enabled']
        search_fields = ['fifo_name', 'fifo_extension']
        ordering_fields = ['fifo_name']

        def get_queryset(self):
            qs = super().get_queryset()
            domain = self.request.query_params.get('domain_uuid')
            if domain:
                qs = qs.filter(domain__domain_uuid=domain)
            return qs

        def get_serializer_class(self):
            if self.action == 'list':
                return FifoListSerializer
            return FifoSerializer
""")

write(os.path.join(d, 'urls.py'), """
    from rest_framework.routers import DefaultRouter
    from .views import FifoViewSet

    router = DefaultRouter()
    router.register(r'', FifoViewSet, basename='fifo')
    urlpatterns = router.urls
""")

write(os.path.join(d, 'admin.py'), """
    from django.contrib import admin
    from .models import Fifo, FifoCallers

    @admin.register(Fifo)
    class FifoAdmin(admin.ModelAdmin):
        list_display = ['fifo_name', 'fifo_extension', 'fifo_strategy', 'fifo_enabled']
        list_filter = ['fifo_enabled']
        search_fields = ['fifo_name']
""")

# ─────────────────────────────────────────────────────────── emergency ──
print('emergency...')
make_app('emergency')
d = os.path.join(BASE, 'emergency')

write(os.path.join(d, 'models.py'), """
    import uuid
    from django.db import models
    from core.models import Domain

    class Emergency(models.Model):
        emergency_uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
        domain = models.ForeignKey(Domain, on_delete=models.CASCADE, null=True, blank=True, db_column='domain_uuid')
        emergency_number = models.CharField(max_length=64)
        emergency_destination = models.CharField(max_length=255, blank=True)
        emergency_context = models.CharField(max_length=128, blank=True)
        emergency_enabled = models.BooleanField(default=True)
        emergency_description = models.TextField(blank=True)
        insert_date = models.DateTimeField(auto_now_add=True)
        insert_user = models.UUIDField(null=True, blank=True)
        update_date = models.DateTimeField(auto_now=True)
        update_user = models.UUIDField(null=True, blank=True)

        class Meta:
            db_table = 'v_emergency'

        def __str__(self):
            return self.emergency_number
""")

write(os.path.join(d, 'serializers.py'), """
    from rest_framework import serializers
    from .models import Emergency

    class EmergencySerializer(serializers.ModelSerializer):
        class Meta:
            model = Emergency
            fields = '__all__'
            read_only_fields = ['emergency_uuid', 'insert_date', 'insert_user', 'update_date', 'update_user']
""")

write(os.path.join(d, 'views.py'), """
    from rest_framework import viewsets, filters
    from django_filters.rest_framework import DjangoFilterBackend
    from .models import Emergency
    from .serializers import EmergencySerializer

    class EmergencyViewSet(viewsets.ModelViewSet):
        queryset = Emergency.objects.all()
        serializer_class = EmergencySerializer
        filter_backends = [DjangoFilterBackend, filters.SearchFilter]
        filterset_fields = ['domain', 'emergency_enabled']
        search_fields = ['emergency_number', 'emergency_destination']

        def get_queryset(self):
            qs = super().get_queryset()
            domain = self.request.query_params.get('domain_uuid')
            if domain:
                qs = qs.filter(domain__domain_uuid=domain)
            return qs
""")

write(os.path.join(d, 'urls.py'), """
    from rest_framework.routers import DefaultRouter
    from .views import EmergencyViewSet

    router = DefaultRouter()
    router.register(r'', EmergencyViewSet, basename='emergency')
    urlpatterns = router.urls
""")

write(os.path.join(d, 'admin.py'), """
    from django.contrib import admin
    from .models import Emergency

    @admin.register(Emergency)
    class EmergencyAdmin(admin.ModelAdmin):
        list_display = ['emergency_number', 'emergency_destination', 'emergency_enabled']
        list_filter = ['emergency_enabled']
        search_fields = ['emergency_number']
""")

# ─────────────────────────────────────────────────────────── event_guard ──
print('event_guard...')
make_app('event_guard')
d = os.path.join(BASE, 'event_guard')

write(os.path.join(d, 'models.py'), """
    import uuid
    from django.db import models
    from core.models import Domain

    class EventGuard(models.Model):
        event_guard_uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
        domain = models.ForeignKey(Domain, on_delete=models.CASCADE, null=True, blank=True, db_column='domain_uuid')
        event_guard_name = models.CharField(max_length=255)
        event_guard_type = models.CharField(max_length=64, blank=True)
        event_guard_expression = models.CharField(max_length=512, blank=True)
        event_guard_action = models.CharField(max_length=64, blank=True)
        event_guard_count = models.IntegerField(default=1)
        event_guard_period = models.IntegerField(default=60)
        event_guard_enabled = models.BooleanField(default=True)
        event_guard_description = models.TextField(blank=True)
        insert_date = models.DateTimeField(auto_now_add=True)
        insert_user = models.UUIDField(null=True, blank=True)
        update_date = models.DateTimeField(auto_now=True)
        update_user = models.UUIDField(null=True, blank=True)

        class Meta:
            db_table = 'v_event_guard'

        def __str__(self):
            return self.event_guard_name
""")

write(os.path.join(d, 'serializers.py'), """
    from rest_framework import serializers
    from .models import EventGuard

    class EventGuardSerializer(serializers.ModelSerializer):
        class Meta:
            model = EventGuard
            fields = '__all__'
            read_only_fields = ['event_guard_uuid', 'insert_date', 'insert_user', 'update_date', 'update_user']
""")

write(os.path.join(d, 'views.py'), """
    from rest_framework import viewsets, filters
    from django_filters.rest_framework import DjangoFilterBackend
    from .models import EventGuard
    from .serializers import EventGuardSerializer

    class EventGuardViewSet(viewsets.ModelViewSet):
        queryset = EventGuard.objects.all()
        serializer_class = EventGuardSerializer
        filter_backends = [DjangoFilterBackend, filters.SearchFilter]
        filterset_fields = ['domain', 'event_guard_enabled', 'event_guard_type']
        search_fields = ['event_guard_name']

        def get_queryset(self):
            qs = super().get_queryset()
            domain = self.request.query_params.get('domain_uuid')
            if domain:
                qs = qs.filter(domain__domain_uuid=domain)
            return qs
""")

write(os.path.join(d, 'urls.py'), """
    from rest_framework.routers import DefaultRouter
    from .views import EventGuardViewSet

    router = DefaultRouter()
    router.register(r'', EventGuardViewSet, basename='event-guard')
    urlpatterns = router.urls
""")

write(os.path.join(d, 'admin.py'), """
    from django.contrib import admin
    from .models import EventGuard

    @admin.register(EventGuard)
    class EventGuardAdmin(admin.ModelAdmin):
        list_display = ['event_guard_name', 'event_guard_type', 'event_guard_enabled']
        list_filter = ['event_guard_type', 'event_guard_enabled']
        search_fields = ['event_guard_name']
""")

# ─────────────────────────────────────────────────────── domain_limits ──
print('domain_limits...')
make_app('domain_limits')
d = os.path.join(BASE, 'domain_limits')

write(os.path.join(d, 'models.py'), """
    import uuid
    from django.db import models
    from core.models import Domain

    class DomainLimit(models.Model):
        domain_limit_uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
        domain = models.ForeignKey(Domain, on_delete=models.CASCADE, db_column='domain_uuid')
        domain_limit_name = models.CharField(max_length=255)
        domain_limit_value = models.CharField(max_length=255, blank=True)
        insert_date = models.DateTimeField(auto_now_add=True)
        insert_user = models.UUIDField(null=True, blank=True)
        update_date = models.DateTimeField(auto_now=True)
        update_user = models.UUIDField(null=True, blank=True)

        class Meta:
            db_table = 'v_domain_limits'

        def __str__(self):
            return f'{self.domain_limit_name}={self.domain_limit_value}'
""")

write(os.path.join(d, 'serializers.py'), """
    from rest_framework import serializers
    from .models import DomainLimit

    class DomainLimitSerializer(serializers.ModelSerializer):
        class Meta:
            model = DomainLimit
            fields = '__all__'
            read_only_fields = ['domain_limit_uuid', 'insert_date', 'insert_user', 'update_date', 'update_user']
""")

write(os.path.join(d, 'views.py'), """
    from rest_framework import viewsets, filters
    from django_filters.rest_framework import DjangoFilterBackend
    from .models import DomainLimit
    from .serializers import DomainLimitSerializer

    class DomainLimitViewSet(viewsets.ModelViewSet):
        queryset = DomainLimit.objects.all()
        serializer_class = DomainLimitSerializer
        filter_backends = [DjangoFilterBackend, filters.SearchFilter]
        filterset_fields = ['domain']
        search_fields = ['domain_limit_name']

        def get_queryset(self):
            qs = super().get_queryset()
            domain = self.request.query_params.get('domain_uuid')
            if domain:
                qs = qs.filter(domain__domain_uuid=domain)
            return qs
""")

write(os.path.join(d, 'urls.py'), """
    from rest_framework.routers import DefaultRouter
    from .views import DomainLimitViewSet

    router = DefaultRouter()
    router.register(r'', DomainLimitViewSet, basename='domain-limit')
    urlpatterns = router.urls
""")

write(os.path.join(d, 'admin.py'), """
    from django.contrib import admin
    from .models import DomainLimit

    @admin.register(DomainLimit)
    class DomainLimitAdmin(admin.ModelAdmin):
        list_display = ['domain', 'domain_limit_name', 'domain_limit_value']
        list_filter = ['domain']
        search_fields = ['domain_limit_name']
""")

# ─────────────────────────────────────────────── modules (modules_app) ──
print('modules_app...')
make_app('modules_app')
d = os.path.join(BASE, 'modules_app')

write(os.path.join(d, 'models.py'), """
    import uuid
    from django.db import models

    class Module(models.Model):
        module_uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
        module_label = models.CharField(max_length=255)
        module_name = models.CharField(max_length=255, unique=True)
        module_category = models.CharField(max_length=128, blank=True)
        module_sequence = models.IntegerField(default=100)
        module_enabled = models.BooleanField(default=True)
        module_default_enabled = models.CharField(max_length=10, default='true')
        module_description = models.TextField(blank=True)
        insert_date = models.DateTimeField(auto_now_add=True)
        update_date = models.DateTimeField(auto_now=True)

        class Meta:
            db_table = 'v_modules'
            ordering = ['module_category', 'module_sequence']

        def __str__(self):
            return self.module_label
""")

write(os.path.join(d, 'serializers.py'), """
    from rest_framework import serializers
    from .models import Module

    class ModuleSerializer(serializers.ModelSerializer):
        class Meta:
            model = Module
            fields = '__all__'
            read_only_fields = ['module_uuid', 'insert_date', 'update_date']
""")

write(os.path.join(d, 'views.py'), """
    from rest_framework import viewsets, filters, status
    from rest_framework.decorators import action
    from rest_framework.response import Response
    from django_filters.rest_framework import DjangoFilterBackend
    from .models import Module
    from .serializers import ModuleSerializer
    from esl.client import get_esl_client

    class ModuleViewSet(viewsets.ModelViewSet):
        queryset = Module.objects.all()
        serializer_class = ModuleSerializer
        filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
        filterset_fields = ['module_category', 'module_enabled']
        search_fields = ['module_name', 'module_label']
        ordering_fields = ['module_category', 'module_sequence']

        @action(detail=True, methods=['post'])
        def load(self, request, pk=None):
            module = self.get_object()
            try:
                esl = get_esl_client()
                result = esl.module_load(module.module_name)
                module.module_enabled = True
                module.save(update_fields=['module_enabled'])
                return Response({'status': 'loaded', 'result': result})
            except Exception as e:
                return Response({'error': str(e)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        @action(detail=True, methods=['post'])
        def unload(self, request, pk=None):
            module = self.get_object()
            try:
                esl = get_esl_client()
                result = esl.module_unload(module.module_name)
                module.module_enabled = False
                module.save(update_fields=['module_enabled'])
                return Response({'status': 'unloaded', 'result': result})
            except Exception as e:
                return Response({'error': str(e)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        @action(detail=True, methods=['post'])
        def reload(self, request, pk=None):
            module = self.get_object()
            try:
                esl = get_esl_client()
                result = esl.module_reload(module.module_name)
                return Response({'status': 'reloaded', 'result': result})
            except Exception as e:
                return Response({'error': str(e)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
""")

write(os.path.join(d, 'urls.py'), """
    from rest_framework.routers import DefaultRouter
    from .views import ModuleViewSet

    router = DefaultRouter()
    router.register(r'', ModuleViewSet, basename='module')
    urlpatterns = router.urls
""")

write(os.path.join(d, 'admin.py'), """
    from django.contrib import admin
    from .models import Module

    @admin.register(Module)
    class ModuleAdmin(admin.ModelAdmin):
        list_display = ['module_label', 'module_name', 'module_category', 'module_enabled']
        list_filter = ['module_category', 'module_enabled']
        search_fields = ['module_name', 'module_label']
""")

print('All fourth-batch apps done!')
