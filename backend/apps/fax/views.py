import os
import logging
from django.http import HttpResponse, FileResponse
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.utils import timezone
from rest_framework import viewsets, filters, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from django_filters.rest_framework import DjangoFilterBackend
from core.mixins import TenantScopedViewSetMixin
from .models import Fax, FaxFile
from .serializers import FaxSerializer, FaxListSerializer, FaxFileSerializer
from .utils import pdf_to_tiff, tiff_to_pdf

logger = logging.getLogger(__name__)





def _resolve_gateway(gateway_input, tenant):
    """
    Return a FreeSWITCH gateway name string.
    gateway_input may be a UUID (from frontend), a plain name, or empty.
    Falls back to the tenant's fax_gateway, then any enabled tenant gateway.
    """
    from apps.gateways.models import Gateway
    import uuid as _uuid

    # Try to treat input as UUID first
    if gateway_input:
        try:
            _uuid.UUID(gateway_input)
            gw = Gateway.objects.filter(gateway_uuid=gateway_input, gateway_enabled=True).first()
            if gw:
                return gw.gateway
        except ValueError:
            # Not a UUID — treat as a literal gateway name
            if not gateway_input.startswith('$'):
                return gateway_input

    # Fall back to tenant's configured fax_gateway
    if tenant and tenant.fax_gateway_id:
        gw = Gateway.objects.filter(gateway_uuid=tenant.fax_gateway_id, gateway_enabled=True).first()
        if gw:
            return gw.gateway

    # Last resort: any enabled gateway for this tenant
    qs = Gateway.objects.filter(gateway_enabled=True)
    if tenant:
        qs = qs.filter(tenant=tenant)
    gw = qs.first()
    return gw.gateway if gw else None


class FaxViewSet(TenantScopedViewSetMixin, viewsets.ModelViewSet):
    queryset = Fax.objects.select_related('tenant', 'domain').prefetch_related('files')
    serializer_class = FaxSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['domain', 'fax_enabled']
    search_fields = ['fax_name', 'fax_extension', 'fax_email']
    ordering_fields = ['fax_name', 'fax_extension']

    def get_serializer_class(self):
        if self.action == 'list':
            return FaxListSerializer
        return FaxSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        scope = self.request.user.fax_box_scope()
        if scope is not None:
            qs = qs.filter(fax_uuid__in=scope)
        return qs

    @action(detail=True, methods=['post'], url_path='send')
    def send_fax(self, request, pk=None):
        """
        Send a fax.

        POST /api/v1/fax/{fax_uuid}/send/
        Multipart form:
          - destination_number: E.164 or local number to dial
          - file: TIFF or PDF file to send
          - gateway: (optional) FreeSWITCH gateway name; defaults to ${default_provider}
        """
        fax = self.get_object()

        destination_number = request.data.get('destination_number', '').strip()
        uploaded_file = request.FILES.get('file')
        gateway = _resolve_gateway(request.data.get('gateway', '').strip(), fax.tenant)

        if not destination_number:
            return Response(
                {'error': 'destination_number is required'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not uploaded_file:
            return Response(
                {'error': 'file is required (TIFF or PDF)'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not gateway:
            return Response(
                {'error': 'No active gateway found. Please configure a gateway first.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Save uploaded file to outbound fax directory
        import tempfile
        outbound_dir = f'/var/lib/freeswitch/fax/outbound/{fax.fax_uuid}'
        try:
            os.makedirs(outbound_dir, exist_ok=True)
        except OSError:
            outbound_dir = tempfile.gettempdir()

        orig_name = uploaded_file.name
        file_ext = os.path.splitext(orig_name)[1].lower()
        if file_ext not in ('.tif', '.tiff', '.pdf'):
            file_ext = '.tif'
        base = os.path.splitext(orig_name)[0].replace(' ', '_')
        file_name = f'{int(timezone.now().timestamp())}_{base}{file_ext}'
        file_path = os.path.join(outbound_dir, file_name)

        try:
            with open(file_path, 'wb') as f:
                for chunk in uploaded_file.chunks():
                    f.write(chunk)
        except OSError as e:
            logger.error(f'FaxSendView: cannot write file: {e}')
            return Response({'error': f'Cannot save file on server: {e}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # txfax only supports TIFF — convert PDF if needed
        if file_ext == '.pdf':
            try:
                file_path = pdf_to_tiff(file_path)
            except RuntimeError as e:
                logger.error(f'FaxSendView: PDF conversion failed: {e}')
                return Response({'error': f'PDF conversion failed: {e}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        ff = FaxFile.objects.create(
            fax=fax,
            tenant=fax.tenant,
            domain=fax.domain,
            fax_file_type=file_ext.lstrip('.'),
            fax_file_name=uploaded_file.name,
            fax_file_path=file_path,
            direction='outbound',
            fax_file_status='pending',
            fax_file_destination_number=destination_number,
            fax_file_date=timezone.now(),
        )

        # Build ESL originate command for txfax
        cid_name = fax.fax_caller_id_name or fax.fax_name
        cid_number = fax.fax_caller_id_number or fax.fax_extension
        originate_vars = (
            f'origination_caller_id_name={cid_name},'
            f'origination_caller_id_number={cid_number},'
            f'fax_ident={cid_name},'
            f'fax_header={cid_name},'
            f'absolute_codec_string=PCMU,'
            f'fax_enable_t38=true,'
            f'fax_enable_t38_request=true,'
            f'fax_disable_v17=false,'
            f'fax_use_ecm=true,'
            f'fax_enable_t38_insist=true'
        )
        originate_cmd = (
            f'originate {{{originate_vars}}}'
            f'sofia/gateway/{gateway}/{destination_number}'
            f' &txfax({file_path})'
        )

        esl_result = ''
        channel_uuid = ''
        try:
            from esl.client import get_esl_client
            esl = get_esl_client()
            esl_result = esl.api(originate_cmd)
            # +OK means FreeSWITCH accepted the originate — the call is in progress.
            # Actual fax delivery is async; status stays 'pending' until FS reports back.
            if esl_result and '+OK' in esl_result:
                ff.fax_file_status = 'pending'
                import re as _re
                m = _re.search(r'\+OK\s+([0-9a-f-]{36})', esl_result)
                if m:
                    channel_uuid = m.group(1)
            else:
                ff.fax_file_status = 'failed'
        except Exception as e:
            logger.error(f'FaxSendView: ESL error: {e}')
            ff.fax_file_status = 'failed'
            esl_result = str(e)

        ff.channel_uuid = channel_uuid
        ff.save(update_fields=['fax_file_status', 'channel_uuid'])

        if ff.fax_file_status == 'pending' and channel_uuid:
            from .tasks import poll_fax_result
            poll_fax_result.apply_async(
                args=[str(ff.fax_file_uuid), channel_uuid],
                countdown=15,
            )

        resp_status = status.HTTP_200_OK if ff.fax_file_status == 'pending' else status.HTTP_400_BAD_REQUEST
        return Response({
            'status': ff.fax_file_status,
            'esl_result': esl_result,
            'fax_file_uuid': str(ff.fax_file_uuid),
            'message': 'Fax queued — delivery pending.' if ff.fax_file_status == 'pending' else 'Fax failed to originate.',
        }, status=resp_status)


class FaxFileViewSet(TenantScopedViewSetMixin, viewsets.ModelViewSet):
    queryset = FaxFile.objects.select_related('tenant', 'domain')
    serializer_class = FaxFileSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['fax', 'fax_file_status']
    search_fields = ['fax_file_name', 'fax_file_destination_number', 'fax_file_caller_id_number']
    ordering_fields = ['fax_file_date', 'insert_date']
    cache_timeout = 0  # Disable caching — quick-send writes bypass the mixin invalidation

    def get_queryset(self):
        qs = super().get_queryset()
        # Restrict files to the user's allowed fax boxes (None = no restriction).
        # download() bypasses get_permissions but still goes through get_queryset
        # via get_object, so per-box scoping is enforced there too.
        scope = getattr(self.request.user, 'fax_box_scope', lambda: None)()
        if scope is not None:
            qs = qs.filter(fax_id__in=scope)
        return qs

    def get_permissions(self):
        # The download action performs its own JWT token validation via ?token= query param
        # (needed for iframe/direct-link access where Authorization headers can't be set).
        # Skip DRF's IsAuthenticated check here so the request reaches the action code.
        if self.action == 'download':
            return []
        return super().get_permissions()

    @action(detail=True, methods=['get'], url_path='download')
    def download(self, request, pk=None):
        """Stream the fax file to the browser.

        Prefers the original PDF (for in-browser preview) over the converted TIFF.
        Use ?attachment=1 to force download instead of inline display.
        Accepts JWT via ?token= query param for iframe/direct-link access.
        """
        # Allow token via query param (iframes can't send Authorization header)
        if not request.user or not request.user.is_authenticated:
            token_str = request.query_params.get('token', '')
            if token_str:
                try:
                    from rest_framework_simplejwt.tokens import AccessToken
                    from core.models import User
                    token = AccessToken(token_str)
                    user = User.objects.get(pk=token['user_uuid'], user_enabled=True)
                    request.user = user
                except Exception:
                    return Response({'error': 'Invalid token.'}, status=status.HTTP_401_UNAUTHORIZED)
            else:
                return Response({'error': 'Authentication required.'}, status=status.HTTP_401_UNAUTHORIZED)

        ff = self.get_object()

        file_path = ff.fax_file_path or ''
        if not file_path or not os.path.isfile(file_path):
            return Response(
                {'error': 'Fax file not found on disk.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        # If the stored file is a TIFF, auto-convert to PDF for universal viewing.
        # The PDF is cached alongside the TIF — conversion only happens once.
        if file_path.lower().endswith('.tif') or file_path.lower().endswith('.tiff'):
            try:
                file_path = tiff_to_pdf(file_path)
            except Exception as conv_err:
                logger.warning('TIFF→PDF conversion failed for %s: %s — serving raw TIFF', file_path, conv_err)
                # Fall back to serving the raw TIFF

        ext = os.path.splitext(file_path)[1].lower()
        content_type = 'application/pdf' if ext == '.pdf' else 'image/tiff'
        disposition = 'attachment' if request.query_params.get('attachment') else 'inline'
        filename = os.path.basename(os.path.splitext(ff.fax_file_path or file_path)[0] + '.pdf')

        response = FileResponse(open(file_path, 'rb'), content_type=content_type)
        response['Content-Disposition'] = f'{disposition}; filename="{filename}"'
        response['X-Frame-Options'] = 'SAMEORIGIN'
        return response


class FaxQuickSendView(APIView):
    """
    Send a fax directly without requiring a saved Fax box.

    POST /api/v1/fax/quick-send/
    Multipart form:
      - destination_number: number to dial
      - file: TIFF or PDF
      - caller_id_name: (optional)
      - caller_id_number: (optional)
      - gateway: (optional) FreeSWITCH gateway name
    """

    def post(self, request, *args, **kwargs):
        destination_number = request.data.get('destination_number', '').strip()
        uploaded_file = request.FILES.get('file')
        caller_id_name = request.data.get('caller_id_name', 'Fax').strip()
        caller_id_number = request.data.get('caller_id_number', '').strip()
        tenant = getattr(request, 'tenant', None)
        # Superusers: always prefer ?tenant= query param over request.tenant
        if request.user.is_superuser:
            tenant_id = request.query_params.get('tenant')
            if tenant_id:
                from core.models import Tenant
                tenant = Tenant.objects.filter(tenant_uuid=tenant_id).first()
        gateway = _resolve_gateway(request.data.get('gateway', '').strip(), tenant)

        if not destination_number:
            return Response({'error': 'destination_number is required'}, status=status.HTTP_400_BAD_REQUEST)
        if not uploaded_file:
            return Response({'error': 'file is required (TIFF or PDF)'}, status=status.HTTP_400_BAD_REQUEST)
        if not gateway:
            return Response({'error': 'No active gateway found. Please configure a gateway first.'}, status=status.HTTP_400_BAD_REQUEST)

        import tempfile
        outbound_dir = '/var/lib/freeswitch/fax/outbound/quick'
        try:
            os.makedirs(outbound_dir, exist_ok=True)
        except OSError as e:
            logger.error(f'FaxQuickSendView: cannot create outbound dir: {e}')
            outbound_dir = tempfile.gettempdir()

        # Ensure file has an extension txfax can process; strip spaces (breaks ESL originate)
        orig_name = uploaded_file.name
        ext = os.path.splitext(orig_name)[1].lower()
        if ext not in ('.tif', '.tiff', '.pdf'):
            ext = '.tif'
        base = os.path.splitext(orig_name)[0].replace(' ', '_')
        file_name = f'{int(timezone.now().timestamp())}_{base}{ext}'
        file_path = os.path.join(outbound_dir, file_name)

        try:
            with open(file_path, 'wb') as fh:
                for chunk in uploaded_file.chunks():
                    fh.write(chunk)
        except OSError as e:
            logger.error(f'FaxQuickSendView: cannot write file: {e}')
            return Response({'error': f'Cannot save file on server: {e}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # txfax only supports TIFF — convert PDF if needed
        if ext == '.pdf':
            try:
                file_path = pdf_to_tiff(file_path)
            except RuntimeError as e:
                logger.error(f'FaxQuickSendView: PDF conversion failed: {e}')
                return Response({'error': f'PDF conversion failed: {e}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        originate_vars = (
            f'origination_caller_id_name={caller_id_name},'
            f'origination_caller_id_number={caller_id_number},'
            f'fax_ident={caller_id_name},'
            f'fax_header={caller_id_name},'
            f'absolute_codec_string=PCMU,'
            f'fax_enable_t38=true,'
            f'fax_enable_t38_request=true,'
            f'fax_disable_v17=false,'
            f'fax_use_ecm=true,'
            f'fax_enable_t38_insist=true'
        )
        originate_cmd = (
            f'originate {{{originate_vars}}}'
            f'sofia/gateway/{gateway}/{destination_number}'
            f' &txfax({file_path})'
        )

        from core.models import Domain
        domain = Domain.objects.filter(tenant=tenant).first() if tenant else None
        file_ext = os.path.splitext(uploaded_file.name)[1].lower().lstrip('.') or 'tif'

        ff = FaxFile.objects.create(
            fax=None,
            tenant=tenant,
            domain=domain,
            fax_file_type=file_ext,
            fax_file_name=uploaded_file.name,
            fax_file_path=file_path,
            direction='outbound',
            fax_file_status='pending',
            fax_file_destination_number=destination_number,
            fax_file_caller_id_name=caller_id_name,
            fax_file_caller_id_number=caller_id_number,
            fax_file_date=timezone.now(),
        )

        esl_result = ''
        fax_status = 'failed'
        channel_uuid = ''
        try:
            from esl.client import get_esl_client
            esl = get_esl_client()
            logger.info(f'FaxQuickSendView: originate_cmd={originate_cmd!r}')
            esl_result = esl.api(originate_cmd)
            logger.info(f'FaxQuickSendView: esl_result={esl_result!r}')
            if esl_result and '+OK' in esl_result:
                fax_status = 'pending'
                import re as _re
                m = _re.search(r'\+OK\s+([0-9a-f-]{36})', esl_result)
                if m:
                    channel_uuid = m.group(1)
        except Exception as e:
            logger.error(f'FaxQuickSendView: ESL error: {e}')
            esl_result = str(e)

        ff.fax_file_status = fax_status
        ff.channel_uuid = channel_uuid
        ff.save(update_fields=['fax_file_status', 'channel_uuid'])
        logger.info(f'FaxQuickSendView: saved fax_file_uuid={ff.fax_file_uuid} status={fax_status} channel_uuid={channel_uuid!r} scheduling_task={fax_status=="pending" and bool(channel_uuid)}')

        if fax_status == 'pending' and channel_uuid:
            from .tasks import poll_fax_result
            poll_fax_result.apply_async(
                args=[str(ff.fax_file_uuid), channel_uuid],
                countdown=15,
            )

        resp_status = status.HTTP_200_OK if fax_status == 'pending' else status.HTTP_400_BAD_REQUEST
        return Response({
            'status': fax_status,
            'esl_result': esl_result,
            'fax_file_uuid': str(ff.fax_file_uuid),
            'message': 'Fax queued — delivery pending.' if fax_status == 'pending' else 'Fax failed to originate.',
        }, status=resp_status)


@method_decorator(csrf_exempt, name='dispatch')
class FaxReceiveWebhookView(View):
    """
    Webhook called by FreeSWITCH after rxfax completes.
    FreeSWITCH posts to /api/v1/fax/received/ via the system/curl action
    in the rxfax dialplan extension generated by generators.py.

    Expected POST fields:
      fax_uuid, fax_file, fax_success, fax_total_pages, fax_result_text,
      caller_id_number, caller_id_name, domain_name, fax_extension
    """

    def post(self, request, *args, **kwargs):
        fax_uuid_str         = request.POST.get('fax_uuid', '')
        fax_file             = request.POST.get('fax_file', '')
        fax_success          = request.POST.get('fax_success', '0')
        # fax_pages comes from ${fax_document_transferred_pages} — the correct spandsp variable.
        # Fall back to fax_total_pages for any old-style callbacks.
        fax_pages_raw        = request.POST.get('fax_pages') or request.POST.get('fax_total_pages', '0')
        fax_result_text      = request.POST.get('fax_result_text', '')
        caller_id_number     = request.POST.get('caller_id_number', '')
        caller_id_name       = request.POST.get('caller_id_name', '')
        domain_name          = request.POST.get('domain_name', '')
        # fax_did_number = real DID (${sip_to_user}); fax_mailbox = box extension.
        # Fall back to fax_extension for any old-style callbacks.
        fax_did_number       = request.POST.get('fax_did_number', '')
        fax_mailbox          = request.POST.get('fax_mailbox') or request.POST.get('fax_extension', '')
        fax_remote_station_id = request.POST.get('fax_remote_station_id') or \
                                request.POST.get('fax_remote_id') or \
                                request.POST.get('fax_header', '')

        logger.info(
            f'Fax received webhook: fax_uuid={fax_uuid_str} '
            f'file={fax_file} success={fax_success} pages={fax_pages_raw} '
            f'did={fax_did_number} mailbox={fax_mailbox}'
        )

        try:
            fax = Fax.objects.get(fax_uuid=fax_uuid_str)
        except (Fax.DoesNotExist, ValueError):
            logger.warning(f'FaxReceiveWebhookView: Fax box not found: {fax_uuid_str}')
            return HttpResponse(status=404)

        file_status = 'received' if fax_success == '1' else 'failed'
        pages = int(fax_pages_raw) if str(fax_pages_raw).isdigit() else 0

        # Prevent duplicate FaxFile creation if the webhook is called multiple times for the same file
        if fax_file and FaxFile.objects.filter(fax_file_path=fax_file).exists():
            logger.info(f'FaxReceiveWebhookView: Duplicate webhook for file {fax_file} — skipping')
            return HttpResponse('OK (Duplicate)')

        ff = FaxFile.objects.create(
            fax=fax,
            tenant=fax.tenant,
            domain=fax.domain,
            fax_file_type='tif',
            fax_file_name=os.path.basename(fax_file) if fax_file else '',
            fax_file_path=fax_file,
            direction='inbound',
            fax_file_status=file_status,
            fax_file_pages=pages,
            fax_file_caller_id_name=caller_id_name,
            fax_file_caller_id_number=caller_id_number,
            # Store the real DID number; fall back to mailbox extension if DID not sent
            fax_file_destination_number=fax_did_number or fax_mailbox,
            fax_file_station_id=fax_remote_station_id,
            fax_file_date=timezone.now(),
        )

        if fax.tenant_id:
            try:
                from apps.client_api.tasks import fire_webhook_event
                event = 'fax.received' if file_status == 'received' else 'fax.failed'
                fire_webhook_event.delay(
                    str(fax.tenant_id), event, str(ff.fax_file_uuid),
                    inline_data={
                        'direction': 'inbound',
                        'fax_file_uuid': str(ff.fax_file_uuid),
                        'fax_uuid': str(fax.fax_uuid),
                        'status': file_status,
                        'pages': pages,
                        'file_size_bytes': ff.file_size_bytes,
                        'caller_id_number': caller_id_number,
                        'destination_number': fax_did_number or fax_mailbox,
                        'mailbox': fax_mailbox,
                    },
                )
            except Exception as wh_exc:
                logger.error(f'FaxReceiveWebhookView: failed to fire webhook: {wh_exc}')

        # Email the fax to the configured fax_email address (if set)
        if file_status == 'received' and fax.fax_email:
            try:
                from .tasks import send_fax_email
                send_fax_email.apply_async(
                    args=[str(ff.fax_file_uuid)],
                    countdown=10,  # Give FreeSWITCH time to finish writing the file
                )
                logger.info(f'FaxReceiveWebhookView: queued send_fax_email for {ff.fax_file_uuid}')
            except Exception as email_exc:
                logger.error(f'FaxReceiveWebhookView: failed to queue send_fax_email: {email_exc}')

        return HttpResponse('OK')

