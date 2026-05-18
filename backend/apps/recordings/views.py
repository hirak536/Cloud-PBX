import base64
import io
import os
import re
import mimetypes
from datetime import datetime, timezone

from django.conf import settings
from django.http import FileResponse, Http404
from rest_framework import viewsets, filters, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from core.mixins import TenantScopedViewSetMixin
from core.models import Domain
from .models import Recording, CallRecording
from .serializers import RecordingSerializer, CallRecordingSerializer


def _save_recording_file(instance):
    """
    If the Recording has recording_base64 data, decode it and write to disk
    at FREESWITCH_SOUNDS_DIR/<recording_filename> so FreeSWITCH can play it.
    """
    if not instance.recording_base64 or not instance.recording_filename:
        return

    sounds_dir = getattr(settings, 'FREESWITCH_SOUNDS_DIR', None)
    if not sounds_dir:
        return

    dest = os.path.join(sounds_dir, instance.recording_filename)
    os.makedirs(os.path.dirname(dest) or sounds_dir, exist_ok=True)

    try:
        audio_data = base64.b64decode(instance.recording_base64)
    except Exception:
        return

    with open(dest, 'wb') as f:
        f.write(audio_data)

# Filename pattern: YYYY-MM-DD-HH-MM-SS_caller_destination.wav
_FNAME_RE = re.compile(
    r'^(\d{4}-\d{2}-\d{2}-\d{2}-\d{2}-\d{2})_(.+?)_(.+?)\.(wav|mp3|ogg)$',
    re.IGNORECASE,
)


class RecordingViewSet(TenantScopedViewSetMixin, viewsets.ModelViewSet):
    queryset = Recording.objects.select_related('tenant', 'domain')
    serializer_class = RecordingSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['domain']
    search_fields = ['recording_name', 'recording_filename']
    ordering_fields = ['recording_name', 'insert_date']


    def perform_create(self, serializer):
        super().perform_create(serializer)
        _save_recording_file(serializer.instance)

    def perform_update(self, serializer):
        super().perform_update(serializer)
        _save_recording_file(serializer.instance)

    @action(detail=True, methods=['get'])
    def stream(self, request, pk=None):
        """Stream or download a media (IVR) recording file from FREESWITCH_SOUNDS_DIR or DB base64."""
        obj = self.get_object()
        content_type, _ = mimetypes.guess_type(obj.recording_filename or '')
        content_type = content_type or 'audio/wav'
        as_attachment = bool(request.query_params.get('download'))
        filename = os.path.basename(obj.recording_filename or 'recording')

        # Try disk first
        sounds_dir = getattr(settings, 'FREESWITCH_SOUNDS_DIR', '')
        path = os.path.join(sounds_dir, obj.recording_filename) if sounds_dir else obj.recording_filename
        if os.path.isfile(path):
            return FileResponse(
                open(path, 'rb'),
                content_type=content_type,
                as_attachment=as_attachment,
                filename=filename,
            )

        # Fall back to base64 stored in DB — and opportunistically write to disk
        # so FreeSWITCH can find the file the next time the IVR is triggered.
        if obj.recording_base64:
            try:
                audio_data = base64.b64decode(obj.recording_base64)
                if sounds_dir and obj.recording_filename:
                    try:
                        os.makedirs(os.path.dirname(path) or sounds_dir, exist_ok=True)
                        with open(path, 'wb') as f:
                            f.write(audio_data)
                    except Exception:
                        pass  # best-effort; FreeSWITCH may still not find it
                return FileResponse(
                    io.BytesIO(audio_data),
                    content_type=content_type,
                    as_attachment=as_attachment,
                    filename=filename,
                )
            except Exception:
                pass

        raise Http404('Recording file not found.')

    @action(detail=False, methods=['post'])
    def record_call(self, request):
        """Originate a call to dial-to-record. ESL integration pending."""
        extension_uuid = request.data.get('extension_uuid')
        external_number = request.data.get('external_number')
        if not extension_uuid and not external_number:
            return Response({'error': 'Provide extension_uuid or external_number.'}, status=status.HTTP_400_BAD_REQUEST)
        # TODO: Use ESL to originate call and record audio
        return Response({'status': 'not_implemented', 'message': 'Dial-to-record requires ESL integration.'}, status=status.HTTP_501_NOT_IMPLEMENTED)


class CallRecordingViewSet(TenantScopedViewSetMixin, viewsets.ReadOnlyModelViewSet):
    queryset = CallRecording.objects.select_related('tenant', 'domain')
    serializer_class = CallRecordingSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['domain']
    search_fields = ['call_recording_caller_id_number', 'call_recording_destination_number']
    ordering_fields = ['call_recording_start_stamp', 'insert_date']

    @action(detail=True, methods=['get'])
    def stream(self, request, pk=None):
        """Stream or download a call recording file."""
        obj = self.get_object()
        path = obj.call_recording_filename
        if not os.path.isabs(path):
            recordings_dir = getattr(settings, 'FREESWITCH_RECORDINGS_DIR', '/var/lib/freeswitch/recordings')
            path = os.path.join(recordings_dir, path)

        if not os.path.isfile(path):
            raise Http404('Recording file not found.')

        content_type, _ = mimetypes.guess_type(path)
        content_type = content_type or 'audio/wav'
        as_attachment = bool(request.query_params.get('download'))
        return FileResponse(
            open(path, 'rb'),
            content_type=content_type,
            as_attachment=as_attachment,
            filename=os.path.basename(path),
        )

    @action(detail=False, methods=['post'], permission_classes=[permissions.AllowAny])
    def ingest(self, request):
        """Called by FreeSWITCH api_hangup_hook after a recorded call ends."""
        file_path = request.POST.get('file') or request.GET.get('file', '')
        caller = request.POST.get('caller') or request.GET.get('caller', '')
        caller_name = request.POST.get('caller_name') or request.GET.get('caller_name', '')
        destination = request.POST.get('destination') or request.GET.get('destination', '')
        domain_name = request.POST.get('domain') or request.GET.get('domain', '')
        duration = request.POST.get('duration') or request.GET.get('duration', '0')
        billsec = request.POST.get('billsec') or request.GET.get('billsec', '0')

        if not file_path or not os.path.isfile(file_path):
            return Response({'detail': 'No valid file path provided.'}, status=status.HTTP_400_BAD_REQUEST)

        if CallRecording.objects.filter(call_recording_filename=file_path).exists():
            return Response({'detail': 'Already ingested.'}, status=status.HTTP_200_OK)

        from core.models import Domain
        domain_obj = Domain.objects.filter(domain_name=domain_name).first() if domain_name else None

        try:
            dur = int(duration)
        except (ValueError, TypeError):
            dur = 0
        try:
            bill = int(billsec)
        except (ValueError, TypeError):
            bill = 0

        rec = CallRecording.objects.create(
            call_recording_filename=file_path,
            call_recording_caller_id_name=caller_name,
            call_recording_caller_id_number=caller,
            call_recording_destination_number=destination,
            call_recording_duration=dur,
            call_recording_billsec=bill,
            domain=domain_obj,
            tenant=domain_obj.tenant if domain_obj else None,
        )
        return Response({'detail': 'Ingested.', 'uuid': str(rec.call_recording_uuid)}, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def sync(self, request):
        """Scan FREESWITCH_RECORDINGS_DIR and import new call recording files into the DB."""
        recordings_dir = getattr(settings, 'FREESWITCH_RECORDINGS_DIR', '/var/lib/freeswitch/recordings')
        if not os.path.isdir(recordings_dir):
            return Response({'error': f'Recordings directory not found: {recordings_dir}'}, status=status.HTTP_400_BAD_REQUEST)

        # Build a set of already-known absolute paths for fast dedup
        existing = set(CallRecording.objects.values_list('call_recording_filename', flat=True))

        created = 0
        skipped = 0

        # Walk: recordings_dir/{domain_name}/{filename}
        for domain_name in os.listdir(recordings_dir):
            domain_path = os.path.join(recordings_dir, domain_name)
            if not os.path.isdir(domain_path):
                continue

            domain_obj = Domain.objects.filter(domain_name=domain_name).first()

            for fname in os.listdir(domain_path):
                abs_path = os.path.join(domain_path, fname)
                if not os.path.isfile(abs_path):
                    continue
                if abs_path in existing or fname in existing:
                    skipped += 1
                    continue

                m = _FNAME_RE.match(fname)
                if not m:
                    skipped += 1
                    continue

                date_str, caller, destination, _ = m.groups()
                try:
                    start_stamp = datetime.strptime(date_str, '%Y-%m-%d-%H-%M-%S').replace(tzinfo=timezone.utc)
                except ValueError:
                    start_stamp = None

                CallRecording.objects.create(
                    call_recording_filename=abs_path,
                    call_recording_caller_id_number=caller,
                    call_recording_destination_number=destination,
                    call_recording_start_stamp=start_stamp,
                    domain=domain_obj,
                    tenant=domain_obj.tenant if domain_obj else None,
                )
                created += 1

        return Response({'created': created, 'skipped': skipped})
