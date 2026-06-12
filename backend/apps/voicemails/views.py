import logging
import os
import time
import wave
from django.http import FileResponse, HttpResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response
from rest_framework.exceptions import NotFound, PermissionDenied
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter
from core.mixins import TenantScopedViewSetMixin
from .models import Voicemail, VoicemailMessage, VoicemailReadState
from .serializers import VoicemailSerializer, VoicemailMessageSerializer

logger = logging.getLogger(__name__)


class VoicemailViewSet(TenantScopedViewSetMixin, viewsets.ModelViewSet):
    queryset = Voicemail.objects.select_related('tenant', 'domain').prefetch_related('options')
    serializer_class = VoicemailSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ['voicemail_enabled']
    search_fields = ['voicemail_id', 'voicemail_mail_to', 'voicemail_description']

    def get_queryset(self):
        from django.db.models import Q
        qs = Voicemail.objects.select_related('tenant', 'domain').prefetch_related('options')
        user = self.request.user

        if user.is_superuser:
            tenant_id = self.request.query_params.get('tenant')
            if tenant_id:
                return qs.filter(Q(tenant_id=tenant_id) | Q(tenant__isnull=True, domain__tenant_id=tenant_id)).distinct()
            return qs

        tenant_id = getattr(user, 'tenant_id', None)
        domain_id = getattr(user, 'domain_id', None)

        if tenant_id:
            # Include records with matching tenant OR tenant=NULL but matching domain
            return qs.filter(Q(tenant_id=tenant_id) | Q(tenant__isnull=True, domain_id=domain_id)).distinct()
        if domain_id:
            return qs.filter(domain_id=domain_id)

        return qs.none()

    @action(detail=True, methods=['post'], url_path='upload_name',
            parser_classes=[MultiPartParser])
    def upload_name(self, request, pk=None):
        """Upload a WAV file to use as the recorded-name greeting."""
        voicemail = self.get_object()
        wav_file = request.FILES.get('file')
        if not wav_file:
            return Response({'detail': 'No file provided.'}, status=status.HTTP_400_BAD_REQUEST)
        if not wav_file.name.lower().endswith('.wav'):
            return Response({'detail': 'Only WAV files are accepted.'}, status=status.HTTP_400_BAD_REQUEST)
        if wav_file.size > 5 * 1024 * 1024:
            return Response({'detail': 'File too large (max 5 MB).'}, status=status.HTTP_400_BAD_REQUEST)

        domain_name = voicemail.domain.domain_name if voicemail.domain else None
        if not domain_name:
            return Response({'detail': 'Voicemail has no domain.'}, status=status.HTTP_400_BAD_REQUEST)

        # Greeting playback in the dialplan reads from the voicemail-UUID dir
        # (see freeswitch_config.generators._voicemail_*; storage_dir is keyed
        # by str(vm.voicemail_uuid), NOT the extension number). Write to the
        # same path or FreeSWITCH will never find the uploaded greeting.
        mailbox = str(voicemail.voicemail_uuid)
        storage_dir = f'/var/lib/freeswitch/storage/voicemail/default/{domain_name}/{mailbox}'
        dest_path = os.path.join(storage_dir, 'recorded_name.wav')

        os.makedirs(storage_dir, exist_ok=True)
        with open(dest_path, 'wb') as f:
            for chunk in wav_file.chunks():
                f.write(chunk)

        return Response({'status': 'saved', 'path': dest_path})


class VoicemailMessageViewSet(viewsets.ViewSet):
    """
    Voicemail message endpoints.

    Messages are stored directly by FreeSWITCH in the voicemail_msgs table.
    Filter by ?username=1001&domain=10.127.127.76 to list a mailbox's messages.

    Endpoints:
      GET    /api/voicemail-messages/             list messages (filter by username/domain)
      POST   /api/voicemail-messages/{uuid}/mark_read/   mark as read
      DELETE /api/voicemail-messages/{uuid}/      delete row + audio file from disk
      GET    /api/voicemail-messages/{uuid}/audio/ stream the audio file
    """
    permission_classes = [permissions.IsAuthenticated]

    def _get_message(self, uuid):
        try:
            return VoicemailMessage.objects.get(uuid=uuid)
        except VoicemailMessage.DoesNotExist:
            raise NotFound('Message not found.')

    def list(self, request):
        qs = VoicemailMessage.objects.all()
        username = request.query_params.get('username')
        domain = request.query_params.get('domain')

        user = request.user
        tenant_id = request.query_params.get('tenant') if user.is_superuser else getattr(user, 'tenant_id', None)

        # Messages are keyed by voicemail UUID (username field = voicemail_uuid).
        # Build allowed UUID set for this tenant — inherently tenant-bound.
        tenant_vm_uuids = None
        if tenant_id:
            vm_qs = Voicemail.objects.filter(tenant_id=tenant_id).values_list('voicemail_uuid', flat=True)
            if not vm_qs.exists():
                # Fallback: match by domain when tenant FK is not set on voicemail
                from core.models import Domain as DomainModel
                domain_names = list(
                    DomainModel.objects.filter(tenant_id=tenant_id).values_list('domain_name', flat=True)
                )
                vm_qs = Voicemail.objects.filter(
                    domain__domain_name__in=domain_names
                ).values_list('voicemail_uuid', flat=True)
            tenant_vm_uuids = set(str(u) for u in vm_qs)

        if username:
            # username may be a voicemail UUID or an old-style extension number
            qs = qs.filter(username=username)
            if tenant_vm_uuids is not None:
                qs = qs.filter(username__in=tenant_vm_uuids)
        elif tenant_vm_uuids is not None:
            qs = qs.filter(username__in=tenant_vm_uuids)

        if domain:
            qs = qs.filter(domain=domain)
        folder = request.query_params.get('folder')
        unread = request.query_params.get('unread')
        if folder:
            qs = qs.filter(in_folder=folder)
        if unread == '1':
            qs = qs.exclude(read_flags='read')

        uuids = list(qs.values_list('uuid', flat=True))
        read_uuids = set(
            VoicemailReadState.objects.filter(
                message_uuid__in=uuids, reader=VoicemailReadState.READER_ADMIN, is_read=True
            ).values_list('message_uuid', flat=True)
        )
        # Build UUID → voicemail_id map to avoid N+1 in serializer
        vm_usernames = set(qs.values_list('username', flat=True))
        uuid_to_voicemail_id = {
            str(vm.voicemail_uuid): vm.voicemail_id
            for vm in Voicemail.objects.filter(voicemail_uuid__in=vm_usernames)
        }
        serializer = VoicemailMessageSerializer(
            qs, many=True,
            context={'read_uuids': read_uuids, 'uuid_to_voicemail_id': uuid_to_voicemail_id},
        )
        return Response(serializer.data)

    def retrieve(self, request, pk=None):
        msg = self._get_message(pk)
        return Response(VoicemailMessageSerializer(msg).data)

    def destroy(self, request, pk=None):
        """Delete the message record and its audio file from disk."""
        msg = self._get_message(pk)
        file_path = msg.file_path
        msg.delete()
        if file_path and os.path.isfile(file_path):
            try:
                os.remove(file_path)
            except OSError:
                pass  # log but don't fail if file already gone
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=['post'], url_path='mark_read')
    def mark_read(self, request, pk=None):
        """Mark a voicemail message as read (stored in PostgreSQL)."""
        VoicemailReadState.objects.update_or_create(
            message_uuid=pk,
            reader=VoicemailReadState.READER_ADMIN,
            defaults={'is_read': True},
        )
        return Response({'status': 'read', 'uuid': pk})

    @action(detail=True, methods=['post'], url_path='mark_unread')
    def mark_unread(self, request, pk=None):
        """Mark a voicemail message as unread (stored in PostgreSQL)."""
        VoicemailReadState.objects.update_or_create(
            message_uuid=pk,
            reader=VoicemailReadState.READER_ADMIN,
            defaults={'is_read': False},
        )
        return Response({'status': 'unread', 'uuid': pk})

    @action(detail=True, methods=['get'], url_path='audio')
    def audio(self, request, pk=None):
        """Stream the voicemail audio file."""
        msg = self._get_message(pk)
        if not msg.file_path or not os.path.isfile(msg.file_path):
            raise NotFound('Audio file not found on disk.')
        response = FileResponse(
            open(msg.file_path, 'rb'),
            content_type='audio/wav',
        )
        filename = os.path.basename(msg.file_path)
        response['Content-Disposition'] = f'inline; filename="{filename}"'
        return response


@method_decorator(csrf_exempt, name='dispatch')
class VoicemailIngestView(View):
    """
    Internal-only endpoint called by FreeSWITCH after recording a voicemail
    in tts_name or recorded_name mode.

    Only accepts requests from 127.0.0.1.

    POST /api/v1/voicemail-messages/ingest/
    Form fields: uuid, username, domain, file_path, cid_name, cid_number, created_epoch
    """

    def post(self, request):
        remote_addr = request.META.get('REMOTE_ADDR', '')
        if remote_addr != '127.0.0.1':
            return HttpResponse('Forbidden', status=403)

        uuid_val = request.POST.get('uuid', '').strip()
        username = request.POST.get('username', '').strip()
        domain = request.POST.get('domain', '').strip()
        file_path = request.POST.get('file_path', '').strip()
        cid_name = request.POST.get('cid_name', '').strip()
        cid_number = request.POST.get('cid_number', '').strip()
        created_epoch_raw = request.POST.get('created_epoch', '')

        if not all([uuid_val, username, domain, file_path]):
            return HttpResponse('Missing required fields', status=400)

        try:
            created_epoch = int(created_epoch_raw)
        except (ValueError, TypeError):
            created_epoch = int(time.time())

        message_len = 0
        if os.path.isfile(file_path):
            try:
                with wave.open(file_path, 'r') as wf:
                    nframes = wf.getnframes()
                    message_len = max(1, round(nframes / wf.getframerate())) if nframes > 0 else 0
            except Exception:
                pass

        try:
            _, created = VoicemailMessage.objects.using('voicemail_sqlite').get_or_create(
                uuid=uuid_val,
                defaults=dict(
                    created_epoch=created_epoch,
                    read_epoch=0,
                    username=username,
                    domain=domain,
                    cid_name=cid_name,
                    cid_number=cid_number,
                    in_folder='inbox',
                    file_path=file_path,
                    message_len=message_len,
                    flags='',
                    read_flags='',
                    forwarded_by='',
                ),
            )
            if not created:
                return HttpResponse('OK', status=200)
        except Exception:
            logger.exception('VoicemailIngestView: failed to insert message %s', uuid_val)
            return HttpResponse('DB error', status=500)

        try:
            from .tasks import transcribe_voicemail_gemini  # noqa: PLC0415
            transcribe_voicemail_gemini.apply_async(
                args=[uuid_val, file_path, username, domain, cid_name, cid_number, message_len, created_epoch],
                countdown=20,
            )
        except Exception:
            logger.exception('VoicemailIngestView: failed to queue transcription for %s', uuid_val)

        return HttpResponse('OK', status=200)
