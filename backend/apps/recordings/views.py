import base64
import io
import os
import re
import wave
import contextlib
import mimetypes
from datetime import datetime, timezone

from django.conf import settings
from urllib.parse import quote
from django.http import FileResponse, Http404, HttpResponse
from rest_framework import viewsets, filters, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from core.mixins import TenantScopedViewSetMixin
from core.models import Domain
from .models import Recording, CallRecording
from .serializers import RecordingSerializer, CallRecordingSerializer


def _xaccel_response(internal_prefix, rel_path, content_type, as_attachment, filename):
    """Hand off byte-serving to Nginx via X-Accel-Redirect.

    Django keeps auth/tenant-scoping; Nginx serves the file with sendfile +
    Range support (fast seeking, worker freed immediately). rel_path is the
    file path relative to the alias root configured on internal_prefix.
    """
    resp = HttpResponse(content_type=content_type)
    # Each segment quoted; Nginx unescapes X-Accel-Redirect before mapping it.
    encoded = '/'.join(quote(seg) for seg in rel_path.split('/'))
    resp['X-Accel-Redirect'] = f'{internal_prefix}{encoded}'
    disp = 'attachment' if as_attachment else 'inline'
    resp['Content-Disposition'] = f'{disp}; filename="{filename}"'
    return resp


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

def _wav_duration(path):
    """Return the duration of a WAV file in whole seconds, or 0 on any failure.

    FreeSWITCH records call audio as WAV, so the stdlib `wave` module reads
    the header without extra deps. Used to backfill duration when it wasn't
    posted by the hangup hook (e.g. rows imported via the sync scanner).
    """
    try:
        with contextlib.closing(wave.open(path, 'rb')) as w:
            rate = w.getframerate()
            if not rate:
                return 0
            return int(round(w.getnframes() / float(rate)))
    except Exception:
        return 0


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
        recordings_dir = getattr(settings, 'FREESWITCH_RECORDINGS_DIR', '/var/lib/freeswitch/recordings')
        path = obj.call_recording_filename
        if not os.path.isabs(path):
            path = os.path.join(recordings_dir, path)

        if not os.path.isfile(path):
            raise Http404('Recording file not found.')

        content_type, _ = mimetypes.guess_type(path)
        content_type = content_type or 'audio/wav'
        as_attachment = bool(request.query_params.get('download'))

        # Serve the file via Nginx (sendfile + Range) rather than pushing 14 MB
        # through the ASGI worker. rel_path is relative to FREESWITCH_RECORDINGS_DIR,
        # which the /protected-recordings/ internal location aliases.
        rel_path = os.path.relpath(os.path.realpath(path), os.path.realpath(recordings_dir))
        if rel_path.startswith('..'):
            # Outside the recordings root — fall back to direct streaming.
            return FileResponse(
                open(path, 'rb'), content_type=content_type,
                as_attachment=as_attachment, filename=os.path.basename(path),
            )
        return _xaccel_response(
            '/protected-recordings/', rel_path, content_type,
            as_attachment, os.path.basename(path),
        )

    @action(detail=False, methods=['get', 'post'], permission_classes=[permissions.AllowAny])
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
        import re as _re
        from django.utils.timezone import datetime as dj_datetime
        import pytz

        from apps.extensions.models import Extension as Ext

        domain_obj = Domain.objects.filter(domain_name=domain_name).first() if domain_name else None

        # Tenant resolution. The FreeSWITCH domain is shared across all tenants
        # here, so domain->tenant is NOT reliable — the extension identity is.
        # Prefer resolving from the extension that appears on either leg
        # (caller for outbound, destination for inbound), matched by sip_username
        # AND scoped to the domain so colliding short-numbers don't cross tenants.
        # Only fall back to the domain's tenant when no extension matches.
        tenant_obj = None
        ext_scope = Ext.objects.exclude(tenant__isnull=True)
        if domain_obj is not None:
            ext_scope = ext_scope.filter(domain=domain_obj.domain_uuid)
        for leg in (caller, destination):
            if not leg:
                continue
            token = leg.split('_')[0]  # strip FreeSWITCH _<uuid> suffix
            ext = ext_scope.filter(sip_username__in=[leg, token]).select_related('tenant').first()
            if ext:
                tenant_obj = ext.tenant
                break

        if tenant_obj is None and domain_obj is not None:
            tenant_obj = domain_obj.tenant

        try:
            dur = int(duration)
        except (ValueError, TypeError):
            dur = 0
        try:
            bill = int(billsec)
        except (ValueError, TypeError):
            bill = 0

        # Parse start_stamp from filename: YYYY-MM-DD-HH-MM-SS_...
        start_stamp = None
        fname = os.path.basename(file_path)
        m = _re.match(r'^(\d{4}-\d{2}-\d{2}-\d{2}-\d{2}-\d{2})_', fname)
        if m:
            try:
                start_stamp = pytz.utc.localize(
                    dj_datetime.strptime(m.group(1), '%Y-%m-%d-%H-%M-%S')
                )
            except ValueError:
                pass

        rec = CallRecording.objects.create(
            call_recording_filename=file_path,
            call_recording_caller_id_name=caller_name,
            call_recording_caller_id_number=caller,
            call_recording_destination_number=destination,
            call_recording_start_stamp=start_stamp,
            call_recording_duration=dur,
            call_recording_billsec=bill,
            domain=domain_obj,
            tenant=tenant_obj,
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

                # Resolve tenant from caller SIP username (e.g. "600-GMD") first,
                # fall back to domain tenant for non-extension callers.
                tenant_obj = None
                if caller:
                    from apps.extensions.models import Extension as _Ext
                    ext = _Ext.objects.filter(sip_username=caller).select_related('tenant').first()
                    if ext:
                        tenant_obj = ext.tenant
                if tenant_obj is None and domain_obj:
                    tenant_obj = domain_obj.tenant

                dur = _wav_duration(abs_path)
                CallRecording.objects.create(
                    call_recording_filename=abs_path,
                    call_recording_caller_id_number=caller,
                    call_recording_destination_number=destination,
                    call_recording_start_stamp=start_stamp,
                    call_recording_duration=dur,
                    call_recording_billsec=dur,
                    domain=domain_obj,
                    tenant=tenant_obj,
                )
                created += 1

        return Response({'created': created, 'skipped': skipped})
