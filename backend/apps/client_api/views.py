"""
Client API views — read-only, tenant-scoped, authenticated via TenantAPIKey.
Also includes superuser-only API Key management views.
"""
import logging
import os
import dateutil.parser as dp
from datetime import datetime, timedelta
import pytz
from django.db.models import Avg, Count, Q, Sum
from rest_framework import permissions, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response
from rest_framework.authentication import SessionAuthentication
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication

from apps.destinations.models import Destination
from apps.extensions.models import Extension
from apps.fax.models import Fax, FaxFile
from apps.voicemails.models import VoicemailMessage, VoicemailReadState
from apps.xml_cdr.models import XmlCdr
from core.models import Tenant

from core.mixins import ClientAPICacheMixin
from .authentication import MasterAPIKeyAuthentication, TenantAPIKeyAuthentication
from .models import TenantAPIKey, WebhookDelivery
from .serializers import (
    ClientCDRSerializer,
    ClientDestinationSerializer,
    ClientExtensionSerializer,
    ClientFaxFileSerializer,
    ClientFaxSerializer,
    ClientTenantSerializer,
    ClientVoicemailMessageSerializer,
    TenantAPIKeyCreateSerializer,
    TenantAPIKeyListSerializer,
    TenantAPIKeyUpdateSerializer,
)

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────

class ClientAPIPermission(permissions.BasePermission):
    """Allow only requests authenticated via TenantAPIKeyAuthentication."""

    def has_permission(self, request, view):
        return (
            request.user is not None
            and hasattr(request.user, 'api_key')
            and request.user.is_authenticated
        )


def _tenant_from_request(request):
    """Extract the tenant from the API key auth user."""
    return request.user.tenant


def _require_tenant(request, tenant_uuid, api_key_tenant):
    """
    Validate the tenant_uuid from the URL matches the api key's tenant.
    Returns the tenant or raises PermissionDenied.
    """
    if str(api_key_tenant.tenant_uuid) != str(tenant_uuid):
        raise PermissionDenied('Tenant UUID does not match this API key.')
    return api_key_tenant


# ──────────────────────────────────────────────
# Client API: Tenant list (master key only)
# ──────────────────────────────────────────────

class MasterKeyPermission(permissions.BasePermission):
    def has_permission(self, request, view):
        if request.user is None or not request.user.is_authenticated:
            return False
        # Session-authenticated superuser
        if getattr(request.user, 'is_superuser', False):
            return True
        # MasterKey header authentication
        return hasattr(request.user, 'master_key')


class ClientTenantListView(APIView):
    authentication_classes = [JWTAuthentication, SessionAuthentication, MasterAPIKeyAuthentication]
    permission_classes = [MasterKeyPermission]

    def get(self, request):
        tenants = Tenant.objects.filter(tenant_enabled=True).order_by('tenant_code')
        from .serializers import ClientTenantSerializer
        return Response(ClientTenantSerializer(tenants, many=True).data)


# ──────────────────────────────────────────────
# Client API: Tenant info
# ──────────────────────────────────────────────

class ClientTenantView(APIView):
    authentication_classes = [TenantAPIKeyAuthentication]
    permission_classes = [ClientAPIPermission]

    def get(self, request):
        tenant = _tenant_from_request(request)
        return Response(ClientTenantSerializer(tenant).data)


# ──────────────────────────────────────────────
# Client API: Extensions
# ──────────────────────────────────────────────

class ClientExtensionView(ClientAPICacheMixin, APIView):
    authentication_classes = [TenantAPIKeyAuthentication]
    permission_classes = [ClientAPIPermission]
    cache_resource = 'extensions'

    def get(self, request, tenant_uuid, extension_uuid=None):
        tenant = _require_tenant(request, tenant_uuid, _tenant_from_request(request))
        suffix = f'detail:{extension_uuid}' if extension_uuid else 'list'
        key = self._ck(tenant_uuid, suffix)
        hit = self._cache_get(key)
        if hit is not None:
            return Response(hit)
        qs = Extension.objects.filter(tenant=tenant)
        enabled_param = request.query_params.get('enabled')
        if enabled_param is not None:
            qs = qs.filter(enabled=enabled_param.lower() == 'true')
        if extension_uuid:
            try:
                obj = qs.get(extension_uuid=extension_uuid)
            except Extension.DoesNotExist:
                raise NotFound()
            data = ClientExtensionSerializer(obj).data
            self._cache_set(key, data)
            return Response(data)
        else:
            qs = qs.order_by('extension')
            from rest_framework.pagination import PageNumberPagination
            paginator = PageNumberPagination()
            paginator.page_size = 20
            paginator.page_size_query_param = 'page_size'
            page = paginator.paginate_queryset(qs, request)
            data = ClientExtensionSerializer(page, many=True).data
            return paginator.get_paginated_response(data)


# ──────────────────────────────────────────────
# Client API: DIDs / Destinations
# ──────────────────────────────────────────────

class ClientDestinationView(ClientAPICacheMixin, APIView):
    authentication_classes = [TenantAPIKeyAuthentication]
    permission_classes = [ClientAPIPermission]
    cache_resource = 'destinations'

    def get(self, request, tenant_uuid, destination_uuid=None):
        tenant = _require_tenant(request, tenant_uuid, _tenant_from_request(request))
        suffix = f'detail:{destination_uuid}' if destination_uuid else 'list'
        key = self._ck(tenant_uuid, suffix)
        hit = self._cache_get(key)
        if hit is not None:
            return Response(hit)
        qs = Destination.objects.filter(tenant=tenant)
        enabled_param = request.query_params.get('enabled')
        if enabled_param is not None:
            qs = qs.filter(destination_enabled=enabled_param.lower() == 'true')
        if destination_uuid:
            try:
                obj = qs.get(destination_uuid=destination_uuid)
            except Destination.DoesNotExist:
                raise NotFound()
            data = ClientDestinationSerializer(obj).data
        else:
            data = ClientDestinationSerializer(qs.order_by('destination_number'), many=True).data
        self._cache_set(key, data)
        return Response(data)


# ──────────────────────────────────────────────
# Client API: CDR
# ──────────────────────────────────────────────

class ClientCDRView(APIView):
    authentication_classes = [TenantAPIKeyAuthentication]
    permission_classes = [ClientAPIPermission]

    _FAILED_CAUSES = (
        'UNALLOCATED_NUMBER', 'NO_ROUTE_TRANSIT_NET', 'NO_ROUTE_DESTINATION',
        'CALL_REJECTED', 'NUMBER_CHANGED', 'DESTINATION_OUT_OF_ORDER',
        'INVALID_NUMBER_FORMAT', 'FACILITY_REJECTED', 'NETWORK_OUT_OF_ORDER',
        'TEMPORARY_FAILURE', 'CHANNEL_UNAVAILABLE', 'OUTGOING_CALL_BARRED',
        'INCOMING_CALL_BARRED', 'BEARER_NOT_AUTHORIZED', 'BEARER_NOT_AVAILABLE',
        'BEARER_NOT_IMPLEMENTED', 'FACILITY_NOT_IMPLEMENTED', 'SERVICE_NOT_IMPLEMENTED',
        'INVALID_CALL_REFERENCE', 'INCOMPATIBLE_DESTINATION', 'INTERWORKING',
        'CRASH', 'SYSTEM_SHUTDOWN', 'LOSE_RACE', 'MANAGER_REQUEST',
        'USER_CHALLENGE', 'MEDIA_TIMEOUT', 'PICKED_OFF',
        'PROGRESS_TIMEOUT', 'GATEWAY_DOWN',
    )
    _CONGESTION_CAUSES = (
        'NORMAL_CIRCUIT_CONGESTION', 'SWITCH_CONGESTION',
        'RESOURCE_UNAVAILABLE', 'SERVICE_UNAVAILABLE',
    )
    _NO_ANSWER_CAUSES = ('NO_ANSWER', 'NO_USER_RESPONSE', 'SUBSCRIBER_ABSENT', 'ALLOTTED_TIMEOUT',
                         'USER_NOT_REGISTERED', 'ORIGINATOR_CANCEL')

    def _extension_only_qs(self, request, tenant):
        """Queryset scoped to tenant + date range + extension + search/number — status is intentionally excluded."""
        qs = XmlCdr.objects.filter(tenant=tenant, leg='a')
        p = request.query_params
        start_gte = p.get('start') or p.get('start_stamp__gte')
        if start_gte:
            qs = qs.filter(start_stamp__gte=start_gte)
        start_lte = p.get('end') or p.get('start_stamp__lte')
        if start_lte:
            qs = qs.filter(start_stamp__lte=start_lte)
        extension = p.get('extension')
        if extension:
            plain_ext = extension.split('-')[0]
            qs = qs.filter(
                Q(extension_number=extension) |
                Q(extension_number=plain_ext) |
                Q(extension_number__startswith=f'{plain_ext}-')
            )
        number = p.get('number')
        if number:
            qs = qs.filter(
                Q(caller_id_number__icontains=number) |
                Q(destination_number__icontains=number)
            )
        search = p.get('search')
        if search:
            qs = qs.filter(
                Q(caller_id_number__icontains=search) |
                Q(caller_id_name__icontains=search) |
                Q(destination_number__icontains=search)
            )
        return qs

    def _filtered_qs(self, request, tenant):
        qs = XmlCdr.objects.filter(tenant=tenant, leg='a')
        p = request.query_params

        direction = p.get('direction')
        if direction:
            qs = qs.filter(direction=direction)

        hangup_cause = p.get('hangup_cause')
        if hangup_cause:
            qs = qs.filter(hangup_cause=hangup_cause)

        status_filter = p.get('status', '').upper()
        if status_filter == 'ANSWERED':
            qs = qs.filter(hangup_cause__in=('NORMAL_CLEARING', 'CALL_AWARDED_DELIVERED'), billsec__gt=0)
        elif status_filter == 'BUSY':
            qs = qs.filter(hangup_cause='USER_BUSY')
        elif status_filter == 'CONGESTION':
            qs = qs.filter(hangup_cause__in=self._CONGESTION_CAUSES)
        elif status_filter == 'NO_ANSWER':
            qs = qs.filter(hangup_cause__in=self._NO_ANSWER_CAUSES).exclude(missed_call=True)
        elif status_filter == 'MISSED':
            qs = qs.filter(hangup_cause__in=self._NO_ANSWER_CAUSES, missed_call=True)
        elif status_filter == 'WENT_TO_VOICEMAIL':
            qs = qs.filter(
                Q(last_app='voicemail') |
                Q(last_app='speak', last_arg__contains='|') |
                Q(last_app='record', last_arg__contains='/voicemail/') |
                Q(last_app='system', last_arg__contains='voicemail-messages/ingest') |
                Q(last_app='phrase', last_arg__contains='voicemail')
            )
        elif status_filter == 'FAILED':
            qs = qs.filter(hangup_cause__in=self._FAILED_CAUSES)

        missed = p.get('missed_call')
        if missed is not None:
            qs = qs.filter(missed_call=missed.lower() == 'true')

        start_gte = p.get('start') or p.get('start_stamp__gte')
        if start_gte:
            qs = qs.filter(start_stamp__gte=start_gte)

        start_lte = p.get('end') or p.get('start_stamp__lte')
        if start_lte:
            qs = qs.filter(start_stamp__lte=start_lte)

        extension = p.get('extension')
        if extension:
            # Match plain extension (inbound: "1001") or SIP username (outbound: "1001-IHS")
            # Strip tenant suffix if caller passed the full SIP username
            plain_ext = extension.split('-')[0]
            qs = qs.filter(
                Q(extension_number=extension) |
                Q(extension_number=plain_ext) |
                Q(extension_number__startswith=f'{plain_ext}-')
            )

        number = p.get('number')
        if number:
            # Match the number against caller_id_number or destination_number
            qs = qs.filter(
                Q(caller_id_number__icontains=number) |
                Q(destination_number__icontains=number)
            )

        search = p.get('search')
        if search:
            qs = qs.filter(
                Q(caller_id_number__icontains=search) |
                Q(caller_id_name__icontains=search) |
                Q(destination_number__icontains=search)
            )
        return qs.order_by('-start_stamp')

    def get(self, request, tenant_uuid, xml_cdr_uuid=None):
        tenant = _require_tenant(request, tenant_uuid, _tenant_from_request(request))

        if xml_cdr_uuid == 'summary':
            return self._summary(request, tenant)

        qs = self._filtered_qs(request, tenant)

        if xml_cdr_uuid:
            try:
                obj = qs.get(xml_cdr_uuid=xml_cdr_uuid)
            except XmlCdr.DoesNotExist:
                raise NotFound()
            return Response(ClientCDRSerializer(obj).data)

        # Pagination
        page = int(request.query_params.get('page', 1))
        page_size = min(int(request.query_params.get('page_size', 25)), 100)
        offset = (page - 1) * page_size
        items = qs[offset:offset + page_size]

        # status_counts always ignore status filter — reflect date range + extension + search/number only.
        # count should always reflect the total calls for the selected extension/date range.
        counts_qs = self._extension_only_qs(request, tenant)
        status_filter = request.query_params.get('status', '').upper()
        # Keep total count of all calls for the selected extension/date range,
        # even when the client filters by status.
        total = counts_qs.count()

        status_counts = counts_qs.aggregate(
            ANSWERED=Count('xml_cdr_uuid', filter=Q(
                hangup_cause__in=('NORMAL_CLEARING', 'CALL_AWARDED_DELIVERED'), billsec__gt=0
            )),
            WENT_TO_VOICEMAIL=Count('xml_cdr_uuid', filter=Q(
                Q(last_app='voicemail') |
                Q(last_app='speak', last_arg__contains='|') |
                Q(last_app='record', last_arg__contains='/voicemail/') |
                Q(last_app='system', last_arg__contains='voicemail-messages/ingest') |
                Q(last_app='phrase', last_arg__contains='voicemail')
            )),
            BUSY=Count('xml_cdr_uuid', filter=Q(hangup_cause='USER_BUSY')),
            CONGESTION=Count('xml_cdr_uuid', filter=Q(hangup_cause__in=(
                'NORMAL_CIRCUIT_CONGESTION', 'SWITCH_CONGESTION',
                'RESOURCE_UNAVAILABLE', 'SERVICE_UNAVAILABLE',
            ))),
            NO_ANSWER=Count('xml_cdr_uuid', filter=Q(
                hangup_cause__in=('NO_ANSWER', 'NO_USER_RESPONSE', 'SUBSCRIBER_ABSENT',
                                  'ALLOTTED_TIMEOUT', 'USER_NOT_REGISTERED', 'ORIGINATOR_CANCEL'),
            ) & ~Q(missed_call=True)),
            MISSED=Count('xml_cdr_uuid', filter=Q(
                hangup_cause__in=('NO_ANSWER', 'NO_USER_RESPONSE', 'SUBSCRIBER_ABSENT',
                                  'ALLOTTED_TIMEOUT', 'USER_NOT_REGISTERED', 'ORIGINATOR_CANCEL'),
                missed_call=True,
            )),
            FAILED=Count('xml_cdr_uuid', filter=Q(hangup_cause__in=(
                'UNALLOCATED_NUMBER', 'NO_ROUTE_TRANSIT_NET', 'NO_ROUTE_DESTINATION',
                'CALL_REJECTED', 'NUMBER_CHANGED', 'DESTINATION_OUT_OF_ORDER',
                'INVALID_NUMBER_FORMAT', 'FACILITY_REJECTED', 'NETWORK_OUT_OF_ORDER',
                'TEMPORARY_FAILURE', 'CHANNEL_UNAVAILABLE', 'OUTGOING_CALL_BARRED',
                'INCOMING_CALL_BARRED', 'BEARER_NOT_AUTHORIZED', 'BEARER_NOT_AVAILABLE',
                'BEARER_NOT_IMPLEMENTED', 'FACILITY_NOT_IMPLEMENTED', 'SERVICE_NOT_IMPLEMENTED',
                'INVALID_CALL_REFERENCE', 'INCOMPATIBLE_DESTINATION', 'INTERWORKING',
                'CRASH', 'SYSTEM_SHUTDOWN', 'LOSE_RACE', 'MANAGER_REQUEST',
                'USER_CHALLENGE', 'MEDIA_TIMEOUT', 'PICKED_OFF',
                'PROGRESS_TIMEOUT', 'GATEWAY_DOWN',
            ))),
        )

        return Response({
            'count': total,
            'page': page,
            'page_size': page_size,
            'status_counts': status_counts,
            'results': ClientCDRSerializer(items, many=True).data,
        })

    def _summary(self, request, tenant):
        qs = self._filtered_qs(request, tenant)
        # Exact same cause lists as the CDR list API status_counts
        _NO_ANSWER_CAUSES = (
            'NO_ANSWER', 'NO_USER_RESPONSE', 'SUBSCRIBER_ABSENT',
            'ALLOTTED_TIMEOUT', 'USER_NOT_REGISTERED', 'ORIGINATOR_CANCEL',
        )
        _FAILED_CAUSES = (
            'UNALLOCATED_NUMBER', 'NO_ROUTE_TRANSIT_NET', 'NO_ROUTE_DESTINATION',
            'CALL_REJECTED', 'NUMBER_CHANGED', 'DESTINATION_OUT_OF_ORDER',
            'INVALID_NUMBER_FORMAT', 'FACILITY_REJECTED', 'NETWORK_OUT_OF_ORDER',
            'TEMPORARY_FAILURE', 'CHANNEL_UNAVAILABLE', 'OUTGOING_CALL_BARRED',
            'INCOMING_CALL_BARRED', 'BEARER_NOT_AUTHORIZED', 'BEARER_NOT_AVAILABLE',
            'BEARER_NOT_IMPLEMENTED', 'FACILITY_NOT_IMPLEMENTED', 'SERVICE_NOT_IMPLEMENTED',
            'INVALID_CALL_REFERENCE', 'INCOMPATIBLE_DESTINATION', 'INTERWORKING',
            'CRASH', 'SYSTEM_SHUTDOWN', 'LOSE_RACE', 'MANAGER_REQUEST',
            'USER_CHALLENGE', 'MEDIA_TIMEOUT', 'PICKED_OFF', 'PROGRESS_TIMEOUT', 'GATEWAY_DOWN',
        )
        _CONGESTION_CAUSES = ('NORMAL_CIRCUIT_CONGESTION', 'SWITCH_CONGESTION', 'RESOURCE_UNAVAILABLE', 'SERVICE_UNAVAILABLE')
        _VOICEMAIL_Q = (
            Q(last_app='voicemail') |
            Q(last_app='speak', last_arg__contains='|') |
            Q(last_app='record', last_arg__contains='/voicemail/') |
            Q(last_app='system', last_arg__contains='voicemail-messages/ingest') |
            Q(last_app='phrase', last_arg__contains='voicemail')
        )

        # Answered = same as CDR list ANSWERED status
        _answered_Q = Q(hangup_cause__in=('NORMAL_CLEARING', 'CALL_AWARDED_DELIVERED'), billsec__gt=0) & ~_VOICEMAIL_Q

        _inbound_Q = Q(direction='inbound')
        _outbound_Q = Q(direction='outbound')

        agg = qs.aggregate(
            total_calls=Count('xml_cdr_uuid'),
            answered_calls=Count('xml_cdr_uuid', filter=_answered_Q),
            # Inbound breakdown — mutually exclusive buckets
            inbound_calls=Count('xml_cdr_uuid', filter=_inbound_Q),
            inbound_answered=Count('xml_cdr_uuid', filter=_inbound_Q & _answered_Q & ~_VOICEMAIL_Q),
            inbound_voicemail=Count('xml_cdr_uuid', filter=_inbound_Q & _VOICEMAIL_Q),
            inbound_missed=Count('xml_cdr_uuid', filter=_inbound_Q & Q(missed_call=True) & ~_VOICEMAIL_Q),
            inbound_no_answer=Count('xml_cdr_uuid', filter=_inbound_Q & Q(hangup_cause__in=_NO_ANSWER_CAUSES) & ~_VOICEMAIL_Q & Q(missed_call=False)),
            inbound_busy=Count('xml_cdr_uuid', filter=_inbound_Q & Q(hangup_cause='USER_BUSY') & ~_VOICEMAIL_Q),
            # Outbound breakdown — mutually exclusive buckets
            outbound_calls=Count('xml_cdr_uuid', filter=_outbound_Q),
            outbound_answered=Count('xml_cdr_uuid', filter=_outbound_Q & _answered_Q),
            outbound_no_answer=Count('xml_cdr_uuid', filter=_outbound_Q & Q(hangup_cause__in=_NO_ANSWER_CAUSES) & ~_answered_Q),
            outbound_busy=Count('xml_cdr_uuid', filter=_outbound_Q & Q(hangup_cause='USER_BUSY') & ~_answered_Q),
            outbound_congestion=Count('xml_cdr_uuid', filter=_outbound_Q & Q(hangup_cause__in=_CONGESTION_CAUSES) & ~_answered_Q),
            outbound_failed=Count('xml_cdr_uuid', filter=_outbound_Q & Q(hangup_cause__in=_FAILED_CAUSES) & ~_answered_Q & ~Q(hangup_cause__in=_NO_ANSWER_CAUSES) & ~Q(hangup_cause='USER_BUSY') & ~Q(hangup_cause__in=_CONGESTION_CAUSES)),
            total_duration=Sum('duration'),
            total_billsec=Sum('billsec'),
            avg_duration=Avg('duration'),
        )
        total = agg['total_calls'] or 0
        answered = agg['answered_calls'] or 0
        inbound = agg['inbound_calls'] or 0
        outbound = agg['outbound_calls'] or 0

        # Voicemail counts — scoped to extension mailbox if extension filter provided,
        # and to the same date range as the CDR filter if provided.
        extension_param = request.query_params.get('extension', '')
        vm_qs = VoicemailMessage.objects.filter(in_folder='inbox')
        if extension_param:
            plain_ext = extension_param.split('-')[0]
            vm_qs = vm_qs.filter(username=plain_ext)
        else:
            domain_names = list(tenant.domains.filter(domain_enabled=True).values_list('domain_name', flat=True))
            vm_qs = vm_qs.filter(domain__in=domain_names)

        # Apply date range using epoch — convert ISO datetime strings to Unix timestamps
        start_gte = request.query_params.get('start') or request.query_params.get('start_stamp__gte')
        start_lte = request.query_params.get('end') or request.query_params.get('start_stamp__lte')
        if start_gte:
            try:
                vm_qs = vm_qs.filter(created_epoch__gte=int(dp.parse(start_gte).timestamp()))
            except Exception:
                pass
        if start_lte:
            try:
                vm_qs = vm_qs.filter(created_epoch__lte=int(dp.parse(start_lte).timestamp()))
            except Exception:
                pass

        try:
            vm_total = vm_qs.count()
            vm_read = vm_qs.filter(read_flags='read').count()
        except Exception:
            vm_total = 0
            vm_read = 0
        vm_unread = vm_total - vm_read

        tenant_counts = {
            'total_did': Destination.objects.filter(tenant=tenant).count(),
            'total_ext': Extension.objects.filter(tenant=tenant).count(),
        }

        return Response({
            'total_did': tenant_counts['total_did'],
            'total_ext': tenant_counts['total_ext'],
            'total_calls': total,
            'total_duration': agg['total_duration'] or 0,
            'total_billsec': agg['total_billsec'] or 0,
            'avg_duration': round(agg['avg_duration'] or 0),
            'answer_rate': round(answered / total * 100, 1) if total else 0.0,
            'outgoing': {
                'total': outbound,
                'answered': agg['outbound_answered'] or 0,
                'no_answer': agg['outbound_no_answer'] or 0,
                'failed': agg['outbound_failed'] or 0,
                'congestion': agg['outbound_congestion'] or 0,
                'busy': agg['outbound_busy'] or 0,
            },
            'incoming': {
                'total': inbound,
                'answered': agg['inbound_answered'] or 0,
                'missed': agg['inbound_missed'] or 0,
                'no_answer': agg['inbound_no_answer'] or 0,
                'busy': agg['inbound_busy'] or 0,
                'voicemail': agg['inbound_voicemail'] or 0,
            },
            'voicemail': {
                'total': vm_total,
                'read': vm_read,
                'unread': vm_unread,
            },
        })


# ──────────────────────────────────────────────
# Client API: CDR Active Extensions
# ──────────────────────────────────────────────

class ClientCDRActiveExtensionsView(APIView):
    authentication_classes = [TenantAPIKeyAuthentication]
    permission_classes = [ClientAPIPermission]

    def get(self, request, tenant_uuid):
        tenant = _require_tenant(request, tenant_uuid, _tenant_from_request(request))
        qs = XmlCdr.objects.filter(tenant=tenant, leg='a')

        start_gte = request.query_params.get('start') or request.query_params.get('start_stamp__gte')
        start_lte = request.query_params.get('end') or request.query_params.get('start_stamp__lte')
        if start_gte:
            qs = qs.filter(start_stamp__gte=start_gte)
        if start_lte:
            qs = qs.filter(start_stamp__lte=start_lte)

        # Build a map from all known identifiers (plain + sip_username) → sip_username
        tenant_exts = Extension.objects.filter(tenant=tenant).values('extension', 'sip_username')
        to_sip = {}
        for ext in tenant_exts:
            sip = ext['sip_username'] or ext['extension']
            to_sip[ext['extension']] = sip
            to_sip[sip] = sip

        # Collect unique sip_usernames from CDR extension_numbers
        cdr_ext_numbers = (
            qs.exclude(extension_number='')
            .values_list('extension_number', flat=True)
            .distinct()
        )
        seen = set()
        active = []
        for e in cdr_ext_numbers:
            normalized = to_sip.get(e)
            if normalized and normalized not in seen:
                seen.add(normalized)
                active.append(normalized)
        active.sort()
        return Response({'extensions': active})


# ──────────────────────────────────────────────
# Client API: Fax
# ──────────────────────────────────────────────

class ClientFaxView(ClientAPICacheMixin, APIView):
    authentication_classes = [TenantAPIKeyAuthentication]
    permission_classes = [ClientAPIPermission]
    cache_resource = 'fax'

    def get(self, request, tenant_uuid, fax_uuid=None):
        tenant = _require_tenant(request, tenant_uuid, _tenant_from_request(request))
        suffix = f'detail:{fax_uuid}' if fax_uuid else 'list'
        key = self._ck(tenant_uuid, suffix)
        hit = self._cache_get(key)
        if hit is not None:
            return Response(hit)
        qs = Fax.objects.filter(tenant=tenant)
        if fax_uuid:
            try:
                obj = qs.get(fax_uuid=fax_uuid)
            except Fax.DoesNotExist:
                raise NotFound()
            data = ClientFaxSerializer(obj).data
        else:
            data = ClientFaxSerializer(qs.order_by('fax_name'), many=True).data
        self._cache_set(key, data)
        return Response(data)


class ClientFaxFileView(APIView):
    authentication_classes = [TenantAPIKeyAuthentication]
    permission_classes = [ClientAPIPermission]

    def get(self, request, tenant_uuid):
        from rest_framework.pagination import PageNumberPagination
        tenant = _require_tenant(request, tenant_uuid, _tenant_from_request(request))
        qs = FaxFile.objects.filter(tenant=tenant).order_by('-fax_file_date')
        status_filter = request.query_params.get('status')
        if status_filter:
            qs = qs.filter(fax_file_status=status_filter)
        direction_filter = request.query_params.get('direction')
        if direction_filter == 'inbound':
            qs = qs.filter(fax_file_status='received')
        elif direction_filter == 'outbound':
            qs = qs.exclude(fax_file_status='received')
        destination_filter = request.query_params.get('destination')
        if destination_filter:
            qs = qs.filter(fax_file_destination_number__icontains=destination_filter)
        search = request.query_params.get('search')
        if search:
            qs = qs.filter(
                Q(fax_file_caller_id_number__icontains=search) |
                Q(fax_file_destination_number__icontains=search) |
                Q(fax_file_name__icontains=search)
            )
        # Compute counts on the unfiltered tenant queryset
        all_qs = FaxFile.objects.filter(tenant=tenant)
        summary = {
            'total':    all_qs.count(),
            'pending':  all_qs.filter(fax_file_status='pending').count(),
            'sent':     all_qs.filter(fax_file_status='sent').count(),
            'received': all_qs.filter(fax_file_status='received').count(),
            'failed':   all_qs.filter(fax_file_status='failed').count(),
        }

        ctx = {'request': request, 'tenant_uuid': tenant_uuid}
        paginator = PageNumberPagination()
        paginator.page_size = 20
        paginator.page_size_query_param = 'page_size'
        page = paginator.paginate_queryset(qs, request)
        response = paginator.get_paginated_response(
            ClientFaxFileSerializer(page, many=True, context=ctx).data
        )
        response.data['summary'] = summary
        return response


class ClientFaxQuickSendView(APIView):
    authentication_classes = [TenantAPIKeyAuthentication]
    permission_classes = [ClientAPIPermission]
    parser_classes = [MultiPartParser]

    def post(self, request, tenant_uuid):
        """
        Send a fax via a saved fax box.

        POST /<tenant_uuid>/fax/quick-send/
        Multipart form:
          - fax_uuid:            UUID of the Fax box to send from
          - destination_number:  Number to dial
          - file:                PDF or TIFF file
          - gateway:             (optional) gateway UUID or name override
        """
        import os, re as _re
        from django.utils import timezone as dj_tz
        from apps.fax.utils import pdf_to_tiff
        from apps.fax.views import _resolve_gateway

        tenant = _require_tenant(request, tenant_uuid, _tenant_from_request(request))
        fax_uuid = request.data.get('fax_uuid', '').strip()
        destination_number = (request.data.get('destination_number') or '').strip()
        file_obj = request.FILES.get('file')
        gateway_input = request.data.get('gateway', '').strip()
        sender_number = request.data.get('sender_number', '').strip()

        if not fax_uuid:
            raise ValidationError({'fax_uuid': 'This field is required.'})
        if not destination_number:
            raise ValidationError({'destination_number': 'This field is required.'})
        if not file_obj:
            raise ValidationError({'file': 'A PDF or TIFF file is required.'})

        try:
            fax = Fax.objects.get(fax_uuid=fax_uuid, tenant=tenant)
        except Fax.DoesNotExist:
            raise NotFound('Fax box not found.')

        gateway = _resolve_gateway(gateway_input, tenant)
        if not gateway:
            raise ValidationError({'gateway': 'No active gateway found. Please configure a gateway first.'})

        # Save uploaded file
        outbound_dir = f'/var/lib/freeswitch/fax/outbound/{fax.fax_uuid}'
        try:
            os.makedirs(outbound_dir, exist_ok=True)
        except OSError:
            import tempfile
            outbound_dir = tempfile.gettempdir()

        orig_name = file_obj.name
        file_ext = os.path.splitext(orig_name)[1].lower()
        if file_ext not in ('.tif', '.tiff', '.pdf'):
            file_ext = '.tif'
        base = os.path.splitext(orig_name)[0].replace(' ', '_')
        file_name = f'{int(dj_tz.now().timestamp())}_{base}{file_ext}'
        file_path = os.path.join(outbound_dir, file_name)

        try:
            with open(file_path, 'wb') as f:
                for chunk in file_obj.chunks():
                    f.write(chunk)
        except OSError as e:
            return Response({'error': f'Cannot save file on server: {e}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # Convert PDF to TIFF if needed
        if file_ext == '.pdf':
            try:
                file_path = pdf_to_tiff(file_path)
            except RuntimeError as e:
                return Response({'error': f'PDF conversion failed: {e}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        ff = FaxFile.objects.create(
            fax=fax,
            tenant=tenant,
            domain=fax.domain,
            fax_file_type=file_ext.lstrip('.'),
            fax_file_name=orig_name,
            fax_file_path=file_path,
            fax_file_status='pending',
            fax_file_destination_number=destination_number,
            fax_file_caller_id_number=sender_number or fax.fax_caller_id_number,
            fax_file_date=dj_tz.now(),
        )

        cid_name = fax.fax_caller_id_name or fax.fax_name
        cid_number = sender_number or fax.fax_caller_id_number or fax.fax_extension
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
        fax_status = 'failed'
        try:
            from esl.client import get_esl_client
            esl = get_esl_client()
            # Use bgapi so the originate returns immediately with a Job-UUID
            # instead of blocking until the fax call completes
            esl_result = esl.api(originate_cmd)
            logger.info(f'ClientFaxQuickSendView: ESL originate result: {esl_result!r}')
            if esl_result and '+OK' in esl_result:
                fax_status = 'pending'
                m = _re.search(r'\+OK\s+([0-9a-f-]{36})', esl_result)
                if m:
                    channel_uuid = m.group(1)
        except Exception as e:
            logger.error(f'ClientFaxQuickSendView: ESL error: {e}')
            esl_result = str(e)

        ff.fax_file_status = fax_status
        ff.channel_uuid = channel_uuid
        ff.save(update_fields=['fax_file_status', 'channel_uuid'])

        if fax_status == 'pending' and channel_uuid:
            from apps.fax.tasks import poll_fax_result
            poll_fax_result.apply_async(
                args=[str(ff.fax_file_uuid), channel_uuid],
                countdown=15,
            )

        resp_status = status.HTTP_202_ACCEPTED if fax_status == 'pending' else status.HTTP_400_BAD_REQUEST
        return Response({
            'fax_file_uuid': str(ff.fax_file_uuid),
            'status': fax_status,
            'message': 'Fax queued — delivery pending.' if fax_status == 'pending' else 'Fax failed to originate.',
        }, status=resp_status)


class ClientFaxFileDetailView(APIView):
    authentication_classes = [TenantAPIKeyAuthentication]
    permission_classes = [ClientAPIPermission]

    def get(self, request, tenant_uuid, fax_file_uuid):
        tenant = _require_tenant(request, tenant_uuid, _tenant_from_request(request))
        try:
            ff = FaxFile.objects.get(fax_file_uuid=fax_file_uuid, tenant=tenant)
        except FaxFile.DoesNotExist:
            raise NotFound('Fax file not found.')
        ctx = {'request': request, 'tenant_uuid': tenant_uuid}
        return Response(ClientFaxFileSerializer(ff, context=ctx).data)


class ClientFaxFileDownloadView(APIView):
    authentication_classes = [TenantAPIKeyAuthentication]
    permission_classes = [ClientAPIPermission]

    def get(self, request, tenant_uuid, fax_file_uuid):
        import os
        from django.http import FileResponse

        tenant = _require_tenant(request, tenant_uuid, _tenant_from_request(request))
        try:
            ff = FaxFile.objects.get(fax_file_uuid=fax_file_uuid, tenant=tenant)
        except FaxFile.DoesNotExist:
            raise NotFound('Fax file not found.')

        file_path = ff.fax_file_path
        # Prefer original PDF over converted TIFF
        if file_path and file_path.endswith('.tif'):
            pdf_path = os.path.splitext(file_path)[0] + '.pdf'
            if os.path.isfile(pdf_path):
                file_path = pdf_path

        if not file_path or not os.path.isfile(file_path):
            raise NotFound('Fax file not found on disk.')

        ext = os.path.splitext(file_path)[1].lower()
        content_type = 'application/pdf' if ext == '.pdf' else 'image/tiff'
        disposition = 'attachment' if request.query_params.get('attachment') else 'inline'
        filename = os.path.basename(file_path)

        response = FileResponse(open(file_path, 'rb'), content_type=content_type)
        response['Content-Disposition'] = f'{disposition}; filename="{filename}"'
        return response


# ──────────────────────────────────────────────
# Client API: Voicemail messages
# ──────────────────────────────────────────────

def _normalize_voicemail_id(voicemail_id, tenant):
    """Strip tenant_code suffix if caller passed e.g. '905-IHDT' instead of '905'."""
    if not voicemail_id:
        return voicemail_id
    tenant_code = getattr(tenant, 'tenant_code', None)
    if tenant_code and voicemail_id.endswith(f'-{tenant_code}'):
        return voicemail_id[: -(len(tenant_code) + 1)]
    return voicemail_id


def _build_voicemail_map(tenant):
    """Return (domain_names_list, vm_map) for a tenant.
    Falls back to Voicemail-linked domains when Domain.tenant FK is not set."""
    from apps.voicemails.models import Voicemail
    from core.models import Domain

    domain_names = list(Domain.objects.filter(tenant=tenant).values_list('domain_name', flat=True))
    if not domain_names:
        domain_names = list(
            Voicemail.objects.filter(tenant=tenant)
            .select_related('domain')
            .values_list('domain__domain_name', flat=True)
            .distinct()
        )

    vm_map = {
        f'{vm.voicemail_id}@{vm.domain.domain_name}': vm.voicemail_id
        for vm in Voicemail.objects.filter(tenant=tenant).select_related('domain', 'tenant')
        if vm.domain
    }
    return domain_names, vm_map


class ClientVoicemailMessageView(APIView):
    authentication_classes = [TenantAPIKeyAuthentication]
    permission_classes = [ClientAPIPermission]

    def _build_voicemail_map(self, tenant):
        return _build_voicemail_map(tenant)

    def get(self, request, tenant_uuid, message_uuid=None):
        tenant = _require_tenant(request, tenant_uuid, _tenant_from_request(request))
        domain_names, voicemail_map = self._build_voicemail_map(tenant)

        if not domain_names:
            return Response([])

        try:
            read_uuids = set(
                VoicemailReadState.objects.filter(
                    reader=VoicemailReadState.READER_CLIENT, is_read=True
                ).values_list('message_uuid', flat=True)
            )
            from apps.voicemails.models import Voicemail as VoicemailModel  # noqa: PLC0415

            voicemail_id_filter = _normalize_voicemail_id(request.query_params.get('voicemail_id'), tenant)

            if not voicemail_id_filter:
                # No mailbox specified — return per-mailbox summary
                mailboxes = VoicemailModel.objects.filter(tenant=tenant).select_related('domain')

                # Messages are keyed by voicemail UUID in the username field
                all_vm_uuids = [str(vm.voicemail_uuid) for vm in mailboxes]
                all_msgs = VoicemailMessage.objects.filter(username__in=all_vm_uuids)

                totals = {
                    row['username']: row['total']
                    for row in all_msgs.values('username').annotate(total=Count('uuid'))
                }
                unread_counts = {
                    row['username']: row['total']
                    for row in all_msgs.exclude(uuid__in=read_uuids).values('username').annotate(total=Count('uuid'))
                }

                summary = []
                for vm in mailboxes:
                    vm_uuid_str = str(vm.voicemail_uuid)
                    summary.append({
                        'voicemail_id': vm.voicemail_id,
                        'total': totals.get(vm_uuid_str, 0),
                        'unread': unread_counts.get(vm_uuid_str, 0),
                    })
                return Response(summary)

            # Single mailbox: find by voicemail_id + tenant, filter messages by its UUID
            vm_obj = VoicemailModel.objects.filter(
                voicemail_id=voicemail_id_filter, tenant=tenant
            ).first()
            if vm_obj is None:
                return Response({'voicemail_id': voicemail_id_filter, 'total': 0, 'unread': 0, 'results': []})
            vm_uuid_str = str(vm_obj.voicemail_uuid)
            all_msgs = VoicemailMessage.objects.filter(username=vm_uuid_str)
            qs = all_msgs

            read_filter = request.query_params.get('read')
            if read_filter is not None:
                want_read = read_filter.lower() == 'true'
                if want_read:
                    qs = qs.filter(uuid__in=read_uuids)
                else:
                    qs = qs.exclude(uuid__in=read_uuids)

            number = request.query_params.get('number')
            if number:
                qs = qs.filter(cid_number__icontains=number)

            search = request.query_params.get('search')
            if search:
                qs = qs.filter(
                    Q(cid_number__icontains=search) |
                    Q(cid_name__icontains=search)
                )

            if message_uuid:
                try:
                    obj = qs.get(uuid=message_uuid)
                except VoicemailMessage.DoesNotExist:
                    raise NotFound()
                ser_ctx = {'read_uuids': read_uuids, 'voicemail_map': voicemail_map,
                           'request': request, 'tenant_uuid': tenant_uuid}
                return Response(ClientVoicemailMessageSerializer(obj, context=ser_ctx).data)

            ser_ctx = {'read_uuids': read_uuids, 'voicemail_map': voicemail_map,
                       'request': request, 'tenant_uuid': tenant_uuid}
            total = qs.count()
            unread = all_msgs.exclude(uuid__in=read_uuids).count()
            from rest_framework.pagination import PageNumberPagination
            paginator = PageNumberPagination()
            paginator.page_size = 20
            paginator.page_size_query_param = 'page_size'
            page = paginator.paginate_queryset(qs, request)
            paginated = paginator.get_paginated_response(
                ClientVoicemailMessageSerializer(page, many=True, context=ser_ctx).data
            )
            paginated.data.update({
                'voicemail_id': voicemail_id_filter,
                'total': total,
                'unread': unread,
            })
            return paginated
        except Exception as e:
            logger.error('ClientVoicemailMessageView.get error: %s', e, exc_info=True)
            return Response({'error': str(e)}, status=500)

    def post(self, request, tenant_uuid, message_uuid=None):
        """Mark a voicemail message as read (POST to .../mark-read/)."""
        if not message_uuid:
            raise ValidationError({'detail': 'message_uuid is required.'})
        tenant = _require_tenant(request, tenant_uuid, _tenant_from_request(request))
        domain_names, _ = self._build_voicemail_map(tenant)
        try:
            msg = VoicemailMessage.objects.get(uuid=message_uuid, domain__in=domain_names)
        except VoicemailMessage.DoesNotExist:
            raise NotFound()

        VoicemailReadState.objects.update_or_create(
            message_uuid=message_uuid,
            reader=VoicemailReadState.READER_CLIENT,
            defaults={'is_read': True},
        )
        read_uuids = VoicemailReadState.objects.filter(
            reader=VoicemailReadState.READER_CLIENT, is_read=True
        ).values_list('message_uuid', flat=True)
        unread = VoicemailMessage.objects.filter(username=msg.username).exclude(uuid__in=read_uuids).count()
        return Response({'status': 'ok', 'unread': unread})

    def patch(self, request, tenant_uuid, message_uuid=None):
        """Mark a voicemail message as read/unread."""
        if not message_uuid:
            raise ValidationError({'detail': 'message_uuid is required.'})
        tenant = _require_tenant(request, tenant_uuid, _tenant_from_request(request))

        read_val = request.data.get('read')
        if read_val is None:
            raise ValidationError({'detail': '"read" field is required.'})

        domain_names, _ = self._build_voicemail_map(tenant)
        try:
            msg = VoicemailMessage.objects.get(uuid=message_uuid, domain__in=domain_names)
        except VoicemailMessage.DoesNotExist:
            raise NotFound()

        VoicemailReadState.objects.update_or_create(
            message_uuid=message_uuid,
            reader=VoicemailReadState.READER_CLIENT,
            defaults={'is_read': bool(read_val)},
        )
        read_uuids = VoicemailReadState.objects.filter(
            reader=VoicemailReadState.READER_CLIENT, is_read=True
        ).values_list('message_uuid', flat=True)
        unread = VoicemailMessage.objects.filter(username=msg.username).exclude(uuid__in=read_uuids).count()
        return Response({'status': 'ok', 'unread': unread})

    def delete(self, request, tenant_uuid, message_uuid=None):
        """Delete a voicemail message and its audio file."""
        if not message_uuid:
            raise ValidationError({'detail': 'message_uuid is required.'})
        tenant = _require_tenant(request, tenant_uuid, _tenant_from_request(request))
        domain_names, _ = self._build_voicemail_map(tenant)

        try:
            msg = VoicemailMessage.objects.get(uuid=message_uuid, domain__in=domain_names)
        except VoicemailMessage.DoesNotExist:
            raise NotFound()

        file_path = msg.file_path
        msg.delete()
        if file_path and os.path.isfile(file_path):
            try:
                os.remove(file_path)
            except OSError:
                pass
        VoicemailReadState.objects.filter(message_uuid=message_uuid, reader=VoicemailReadState.READER_CLIENT).delete()
        return Response(status=204)


# ──────────────────────────────────────────────
# Client API: Voicemail audio stream
# ──────────────────────────────────────────────

class ClientVoicemailAudioView(APIView):
    authentication_classes = [TenantAPIKeyAuthentication]
    permission_classes = [ClientAPIPermission]

    def get(self, request, tenant_uuid, message_uuid):
        import os
        from django.http import FileResponse
        tenant = _require_tenant(request, tenant_uuid, _tenant_from_request(request))
        domain_names, _ = _build_voicemail_map(tenant)
        try:
            msg = VoicemailMessage.objects.get(uuid=message_uuid, domain__in=domain_names)
        except VoicemailMessage.DoesNotExist:
            raise NotFound()
        path = msg.file_path
        if not path or not os.path.exists(path):
            raise NotFound()
        ext = os.path.splitext(path)[1].lower()
        content_type = {
            '.wav': 'audio/wav',
            '.mp3': 'audio/mpeg',
            '.ogg': 'audio/ogg',
            '.mp4': 'audio/mp4',
        }.get(ext, 'audio/wav')
        return FileResponse(open(path, 'rb'), content_type=content_type,
                            as_attachment=False,
                            filename=os.path.basename(path))


# ──────────────────────────────────────────────
# Client API: Voicemail unread counts
# ──────────────────────────────────────────────

class ClientVoicemailUnreadCountsView(APIView):
    authentication_classes = [TenantAPIKeyAuthentication]
    permission_classes = [ClientAPIPermission]

    def get(self, request, tenant_uuid):
        tenant = _require_tenant(request, tenant_uuid, _tenant_from_request(request))
        domain_names, _ = _build_voicemail_map(tenant)

        if not domain_names:
            return Response({})

        from django.db import OperationalError as DjOperationalError
        try:
            read_uuids = VoicemailReadState.objects.filter(
                reader=VoicemailReadState.READER_CLIENT, is_read=True
            ).values_list('message_uuid', flat=True)

            voicemail_id_filter = _normalize_voicemail_id(request.query_params.get('voicemail_id'), tenant)
            from apps.voicemails.models import Voicemail as VoicemailModel  # noqa: PLC0415
            vm_qs = VoicemailModel.objects.filter(tenant=tenant)
            if voicemail_id_filter:
                vm_qs = vm_qs.filter(voicemail_id=voicemail_id_filter)
            # Map voicemail UUID → voicemail_id for the response
            uuid_to_id = {str(vm.voicemail_uuid): vm.voicemail_id for vm in vm_qs}
            messages_qs = VoicemailMessage.objects.filter(username__in=uuid_to_id.keys())

            # Single DB aggregation — count unread per username (voicemail UUID)
            raw_counts = {
                row['username']: row['unread']
                for row in messages_qs
                .exclude(uuid__in=read_uuids)
                .values('username')
                .annotate(unread=Count('uuid'))
            }
            # Return keyed by voicemail_id (human-readable) instead of UUID
            counts = {uuid_to_id[u]: c for u, c in raw_counts.items() if u in uuid_to_id}
            return Response(counts)
        except DjOperationalError:
            return Response({})


# ──────────────────────────────────────────────
# Superuser: API Key Management
# ──────────────────────────────────────────────

class APIKeyManagementView(APIView):
    authentication_classes = [JWTAuthentication, SessionAuthentication, MasterAPIKeyAuthentication]
    permission_classes = [MasterKeyPermission]

    def get(self, request):
        tenant_id = request.query_params.get('tenant')
        qs = TenantAPIKey.objects.select_related('tenant', 'created_by')
        if tenant_id:
            qs = qs.filter(tenant_id=tenant_id)
        return Response(TenantAPIKeyListSerializer(qs, many=True).data)

    def post(self, request):
        ser = TenantAPIKeyCreateSerializer(data=request.data, context={'request': request})
        ser.is_valid(raise_exception=True)
        instance = ser.save()
        plaintext = getattr(instance, '_plaintext', None)
        data = TenantAPIKeyListSerializer(instance).data
        data['api_key'] = plaintext  # shown once only
        # Fire key.generated webhook
        from .models import WebhookDelivery
        from .tasks import _deliver_webhook
        keys = TenantAPIKey.objects.filter(tenant=instance.tenant, is_active=True, webhook_url__gt='').exclude(pk=instance.pk)
        key_payload = {
            'event': 'key.generated',
            'tenant_id': str(instance.tenant_id),
            'tenant_code': instance.tenant.tenant_code,
            'tenant_name': instance.tenant.tenant_name,
            'api_key': plaintext,
        }
        for api_key in keys:
            delivery = WebhookDelivery.objects.create(api_key=api_key, event='key.generated', payload=key_payload)
            _deliver_webhook.delay(str(delivery.id))
        return Response(data, status=status.HTTP_201_CREATED)


class APIKeyDetailView(APIView):
    authentication_classes = [JWTAuthentication, SessionAuthentication, MasterAPIKeyAuthentication]
    permission_classes = [MasterKeyPermission]

    def _get_key(self, pk):
        try:
            return TenantAPIKey.objects.select_related('tenant').get(pk=pk)
        except TenantAPIKey.DoesNotExist:
            raise NotFound()

    def get(self, request, pk):
        return Response(TenantAPIKeyListSerializer(self._get_key(pk)).data)

    def patch(self, request, pk):
        instance = self._get_key(pk)
        ser = TenantAPIKeyUpdateSerializer(instance, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        ser.save()
        # If deactivated, fire key.revoked
        if 'is_active' in request.data and not request.data['is_active']:
            from .tasks import fire_webhook_event
            fire_webhook_event.delay(str(instance.tenant_id), 'key.revoked', str(instance.id))
        return Response(TenantAPIKeyListSerializer(instance).data)

    def delete(self, request, pk):
        instance = self._get_key(pk)
        from .tasks import fire_webhook_event
        fire_webhook_event.delay(str(instance.tenant_id), 'key.revoked', str(instance.id))
        instance.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ──────────────────────────────────────────────
# Superuser: System Log
# ──────────────────────────────────────────────

class SystemLogView(APIView):
    """
    Superuser-only endpoint that returns recent ihspbx service log lines
    by running journalctl on demand.

    GET /api/v1/client/system-log/?lines=200&level=ERROR
    """
    authentication_classes = [JWTAuthentication, SessionAuthentication]
    permission_classes = [permissions.IsAuthenticated, permissions.IsAdminUser]

    def get(self, request):
        if not request.user.is_superuser:
            raise PermissionDenied()

        try:
            lines = max(10, min(int(request.query_params.get('lines', 200)), 1000))
        except (ValueError, TypeError):
            lines = 200

        level_filter = request.query_params.get('level', '').upper().strip()

        import subprocess  # noqa: PLC0415
        try:
            result = subprocess.run(
                ['journalctl', '-u', 'ihspbx', f'-n', str(lines), '--no-pager', '--output=short-iso'],
                capture_output=True, text=True, timeout=10,
            )
            raw_lines = result.stdout.splitlines()
        except Exception as exc:
            logger.error('SystemLogView: journalctl failed: %s', exc)
            return Response({'error': str(exc)}, status=500)

        parsed = []
        for line in raw_lines:
            level = 'INFO'
            upper = line.upper()
            if 'ERROR' in upper or 'EXCEPTION' in upper or 'TRACEBACK' in upper or 'CRITICAL' in upper:
                level = 'ERROR'
            elif 'WARNING' in upper or 'WARN' in upper:
                level = 'WARNING'
            elif 'DEBUG' in upper:
                level = 'DEBUG'
            parsed.append({'line': line, 'level': level})

        if level_filter and level_filter in ('ERROR', 'WARNING', 'DEBUG', 'INFO'):
            parsed = [p for p in parsed if p['level'] == level_filter]

        return Response({'lines': parsed, 'total': len(parsed)})


# ──────────────────────────────────────────────
# Client API: Hourly Call Stats
# ──────────────────────────────────────────────

class ClientCDRHourlyStatsView(APIView):
    """
    POST /<tenant_uuid>/cdr/hourly-stats/

    Body:
        {
            "date":      "2026-04-06",          # ISO date (YYYY-MM-DD)
            "utc_offset": "+05:30",             # UTC offset, e.g. "+05:30", "-07:00", "+00:00"
            "extension":  "1001"                # extension number to filter
        }

    Returns 24 hourly buckets in the user's local time.
    """
    authentication_classes = [TenantAPIKeyAuthentication]
    permission_classes = [ClientAPIPermission]

    def get(self, request, tenant_uuid):
        tenant = _require_tenant(request, tenant_uuid, _tenant_from_request(request))

        # ── Validate inputs ──────────────────────────────────────────────
        date_str = (request.query_params.get('date') or '').strip()
        offset_str = (request.query_params.get('utc_offset') or '').strip()
        extension = (request.query_params.get('extension') or '').strip()

        if not date_str:
            raise ValidationError({'date': 'This field is required.'})
        if not offset_str:
            raise ValidationError({'utc_offset': 'This field is required. E.g. "+05:30" or "-07:00"'})
        if not extension:
            raise ValidationError({'extension': 'This field is required.'})

        try:
            tz = pytz.FixedOffset(_parse_utc_offset_minutes(offset_str))
        except ValueError as e:
            raise ValidationError({'utc_offset': str(e)})

        try:
            parsed_dt = dp.parse(date_str)
            if parsed_dt.tzinfo is not None:
                # Has offset — convert to local tz to get correct local date
                local_date = parsed_dt.astimezone(tz).date()
            elif 'T' in date_str or ' ' in date_str.strip():
                # No offset but has time component — treat as UTC, convert to local
                local_date = pytz.utc.localize(parsed_dt).astimezone(tz).date()
            else:
                # Plain date string e.g. "2026-04-06" — use as-is
                local_date = parsed_dt.date()
        except Exception:
            raise ValidationError({'date': 'Invalid date format. Use ISO format e.g. 2026-04-06 or 2026-04-06T14:30:00-05:00.'})

        # ── Compute UTC window for the full local day ────────────────────
        local_midnight = datetime(local_date.year, local_date.month, local_date.day, 0, 0, 0)
        local_midnight = tz.localize(local_midnight)
        local_end = local_midnight + timedelta(days=1)

        utc_start = local_midnight.astimezone(pytz.utc)
        utc_end = local_end.astimezone(pytz.utc)

        # If the requested date is today in the user's timezone, cap at now
        now_local = datetime.now(tz)
        is_today = now_local.date() == local_date
        current_local_hour = now_local.hour if is_today else 23
        if is_today:
            utc_end = min(utc_end, now_local.astimezone(pytz.utc))

        # ── Query CDR ────────────────────────────────────────────────────
        plain_ext = extension.split('-')[0]
        qs = XmlCdr.objects.filter(
            tenant=tenant,
            start_stamp__gte=utc_start,
            start_stamp__lt=utc_end,
        ).filter(
            Q(extension_number=extension) |
            Q(extension_number=plain_ext) |
            Q(extension_number__startswith=f'{plain_ext}-')
        ).values_list('start_stamp', flat=True)

        # ── Bucket by local hour ─────────────────────────────────────────
        buckets = [0] * 24
        for utc_ts in qs:
            if utc_ts is None:
                continue
            if utc_ts.tzinfo is None:
                utc_ts = pytz.utc.localize(utc_ts)
            local_ts = utc_ts.astimezone(tz)
            buckets[local_ts.hour] += 1

        hours = []
        def _fmt_hour(h):
            suffix = 'am' if h < 12 else 'pm'
            display = h % 12 or 12
            return f'{display}{suffix}'

        for h in range(current_local_hour + 1):
            hours.append({
                'hour': h,
                'label': f'{_fmt_hour(h)}–{_fmt_hour((h + 1) % 24)}',
                'calls': buckets[h],
            })

        return Response({
            'date': local_date.strftime('%Y-%m-%d'),
            'local_date_display': local_midnight.strftime('%B %d, %Y'),
            'local_day_start': local_midnight.strftime('%Y-%m-%dT%H:%M:%S') + offset_str,
            'local_day_end': (local_midnight + timedelta(days=1) - timedelta(seconds=1)).strftime('%Y-%m-%dT%H:%M:%S') + offset_str,
            'utc_offset': offset_str,
            'extension': extension,
            'total': sum(buckets),
            'hours': hours,
        })


# ──────────────────────────────────────────────
# Client API: Daily CDR Summary
# ──────────────────────────────────────────────

class ClientCDRDailySummaryView(APIView):
    """
    GET /<tenant_uuid>/cdr/daily-summary/

    Query params:
      - start:     ISO datetime (required)
      - end:       ISO datetime (required)
      - extension: extension number or SIP username (optional)
      - utc_offset: e.g. "-5", "+05:30" (optional, defaults to UTC)

    Returns per-day breakdown with incoming/outgoing tree structure.
    """
    authentication_classes = [TenantAPIKeyAuthentication]
    permission_classes = [ClientAPIPermission]

    def get(self, request, tenant_uuid):
        tenant = _require_tenant(request, tenant_uuid, _tenant_from_request(request))

        start_str = (request.query_params.get('start') or '').strip()
        end_str = (request.query_params.get('end') or '').strip()
        extension = (request.query_params.get('extension') or '').strip()
        offset_str = (request.query_params.get('utc_offset') or '+00:00').strip()

        if not start_str:
            raise ValidationError({'start': 'This field is required.'})
        if not end_str:
            raise ValidationError({'end': 'This field is required.'})

        try:
            utc_start = dp.parse(start_str).astimezone(pytz.utc)
        except Exception:
            raise ValidationError({'start': 'Invalid ISO datetime format.'})
        try:
            utc_end = dp.parse(end_str).astimezone(pytz.utc)
        except Exception:
            raise ValidationError({'end': 'Invalid ISO datetime format.'})

        try:
            tz = pytz.FixedOffset(_parse_utc_offset_minutes(offset_str))
        except ValueError as e:
            raise ValidationError({'utc_offset': str(e)})

        # Base queryset
        qs = XmlCdr.objects.filter(
            tenant=tenant,
            leg='a',
            start_stamp__gte=utc_start,
            start_stamp__lt=utc_end,
        )
        if extension:
            plain_ext = extension.split('-')[0]
            qs = qs.filter(
                Q(extension_number=extension) |
                Q(extension_number=plain_ext) |
                Q(extension_number__startswith=f'{plain_ext}-')
            )

        from django.db.models.functions import TruncDate
        from datetime import timedelta as td

        _NO_ANSWER_CAUSES = ('NO_ANSWER', 'NO_USER_RESPONSE', 'SUBSCRIBER_ABSENT', 'ALLOTTED_TIMEOUT', 'USER_NOT_REGISTERED', 'ORIGINATOR_CANCEL')
        _FAILED_CAUSES = (
            'UNALLOCATED_NUMBER', 'NO_ROUTE_TRANSIT_NET', 'NO_ROUTE_DESTINATION',
            'CALL_REJECTED', 'NUMBER_CHANGED', 'DESTINATION_OUT_OF_ORDER',
            'INVALID_NUMBER_FORMAT', 'FACILITY_REJECTED', 'NETWORK_OUT_OF_ORDER',
            'TEMPORARY_FAILURE', 'CHANNEL_UNAVAILABLE', 'OUTGOING_CALL_BARRED',
            'INCOMING_CALL_BARRED', 'BEARER_NOT_AUTHORIZED', 'BEARER_NOT_AVAILABLE',
            'BEARER_NOT_IMPLEMENTED', 'FACILITY_NOT_IMPLEMENTED', 'SERVICE_NOT_IMPLEMENTED',
            'INVALID_CALL_REFERENCE', 'INCOMPATIBLE_DESTINATION', 'INTERWORKING',
            'CRASH', 'SYSTEM_SHUTDOWN', 'LOSE_RACE', 'MANAGER_REQUEST',
            'USER_CHALLENGE', 'MEDIA_TIMEOUT', 'PICKED_OFF', 'PROGRESS_TIMEOUT', 'GATEWAY_DOWN',
        )
        _CONGESTION_CAUSES = ('NORMAL_CIRCUIT_CONGESTION', 'SWITCH_CONGESTION', 'RESOURCE_UNAVAILABLE', 'SERVICE_UNAVAILABLE')
        _VOICEMAIL_Q = (
            Q(last_app='voicemail') |
            Q(last_app='speak', last_arg__contains='|') |
            Q(last_app='record', last_arg__contains='/voicemail/') |
            Q(last_app='system', last_arg__contains='voicemail-messages/ingest') |
            Q(last_app='phrase', last_arg__contains='voicemail')
        )
        _answered_Q = Q(hangup_cause__in=('NORMAL_CLEARING', 'CALL_AWARDED_DELIVERED'), billsec__gt=0) & ~_VOICEMAIL_Q
        _inbound_Q = Q(direction='inbound')
        _outbound_Q = Q(direction='outbound')

        # TruncDate with pytz.FixedOffset fails in Postgres.
        # Instead annotate with UTC date, fetch all rows, then re-bucket by local date in Python.
        # To keep it fast we still do all aggregation in the DB — grouped by UTC date.
        # Then shift UTC dates to local dates (handles timezone boundary crossings).

        # Single DB query — group by UTC date
        rows = (
            qs
            .annotate(local_date=TruncDate('start_stamp'))  # UTC date
            .values('local_date')
            .annotate(
                total=Count('xml_cdr_uuid'),
                in_total=Count('xml_cdr_uuid', filter=_inbound_Q),
                in_answered=Count('xml_cdr_uuid', filter=_inbound_Q & _answered_Q),
                in_voicemail=Count('xml_cdr_uuid', filter=_inbound_Q & _VOICEMAIL_Q),
                in_missed=Count('xml_cdr_uuid', filter=_inbound_Q & Q(missed_call=True) & ~_VOICEMAIL_Q),
                in_no_answer=Count('xml_cdr_uuid', filter=_inbound_Q & Q(hangup_cause__in=_NO_ANSWER_CAUSES) & ~_VOICEMAIL_Q & Q(missed_call=False)),
                in_busy=Count('xml_cdr_uuid', filter=_inbound_Q & Q(hangup_cause='USER_BUSY') & ~_VOICEMAIL_Q),
                out_total=Count('xml_cdr_uuid', filter=_outbound_Q),
                out_answered=Count('xml_cdr_uuid', filter=_outbound_Q & _answered_Q),
                out_no_answer=Count('xml_cdr_uuid', filter=_outbound_Q & Q(hangup_cause__in=_NO_ANSWER_CAUSES) & ~_answered_Q),
                out_busy=Count('xml_cdr_uuid', filter=_outbound_Q & Q(hangup_cause='USER_BUSY') & ~_answered_Q),
                out_congestion=Count('xml_cdr_uuid', filter=_outbound_Q & Q(hangup_cause__in=_CONGESTION_CAUSES) & ~_answered_Q),
                out_failed=Count('xml_cdr_uuid', filter=_outbound_Q & Q(hangup_cause__in=_FAILED_CAUSES) & ~_answered_Q & ~Q(hangup_cause__in=_NO_ANSWER_CAUSES) & ~Q(hangup_cause='USER_BUSY') & ~Q(hangup_cause__in=_CONGESTION_CAUSES)),
                total_duration=Sum('duration'),
                total_billsec=Sum('billsec'),
            )
            .order_by('local_date')
        )

        # Re-bucket by local date — UTC midnight shifted by offset may cross a day boundary.
        # For most cases UTC date == local date; for edge cases (e.g. UTC-5 at 23:00 UTC)
        # the local date is one day behind. We approximate by shifting the UTC date by the offset.
        offset_minutes = _parse_utc_offset_minutes(offset_str)
        offset_delta = td(minutes=offset_minutes)

        day_buckets = {}
        for row in rows:
            utc_date = row['local_date']
            if utc_date is None:
                continue
            # Shift UTC date to local date
            local_date = (utc_date + offset_delta).date() if hasattr(utc_date, 'date') else utc_date
            day_str = local_date.isoformat() if hasattr(local_date, 'isoformat') else str(local_date)
            if day_str not in day_buckets:
                day_buckets[day_str] = row
            else:
                # Merge rows that map to the same local date (rare edge case)
                existing = day_buckets[day_str]
                for key in ('total', 'in_total', 'in_answered', 'in_voicemail', 'in_missed',
                            'in_no_answer', 'in_busy', 'out_total', 'out_answered',
                            'out_no_answer', 'out_busy', 'out_congestion', 'out_failed',
                            'total_duration', 'total_billsec'):
                    existing[key] = (existing.get(key) or 0) + (row.get(key) or 0)

        # Fill all days in range — even days with zero calls
        local_start = utc_start.astimezone(tz).date()
        local_end = utc_end.astimezone(tz).date()
        results = []
        current = local_start
        while current <= local_end:
            day_str = current.isoformat()
            b = day_buckets.get(day_str)
            if b:
                total = b['total']
                answered = (b['in_answered'] or 0) + (b['out_answered'] or 0)
                results.append({
                    'date': day_str,
                    'total_calls': total,
                    'total_incoming': b['in_total'] or 0,
                    'total_outgoing': b['out_total'] or 0,
                    'answer_rate': round(answered / total * 100, 1) if total else 0.0,
                    'total_duration': b['total_duration'] or 0,
                    'total_billsec': b['total_billsec'] or 0,
                    'outgoing': {
                        'total': b['out_total'] or 0,
                        'answered': b['out_answered'] or 0,
                        'no_answer': b['out_no_answer'] or 0,
                        'failed': b['out_failed'] or 0,
                        'congestion': b['out_congestion'] or 0,
                        'busy': b['out_busy'] or 0,
                    },
                    'incoming': {
                        'total': b['in_total'] or 0,
                        'answered': b['in_answered'] or 0,
                        'missed': b['in_missed'] or 0,
                        'no_answer': b['in_no_answer'] or 0,
                        'busy': b['in_busy'] or 0,
                        'voicemail': b['in_voicemail'] or 0,
                    },
                })
            else:
                results.append({
                    'date': day_str,
                    'total_calls': 0,
                    'total_incoming': 0,
                    'total_outgoing': 0,
                    'answer_rate': 0.0,
                    'total_duration': 0,
                    'total_billsec': 0,
                    'outgoing': {'total': 0, 'answered': 0, 'no_answer': 0, 'failed': 0, 'congestion': 0, 'busy': 0},
                    'incoming': {'total': 0, 'answered': 0, 'missed': 0, 'no_answer': 0, 'busy': 0, 'voicemail': 0},
                })
            current += td(days=1)

        total_incoming = sum(r['total_incoming'] for r in results)
        total_outgoing = sum(r['total_outgoing'] for r in results)
        total_calls = total_incoming + total_outgoing
        total_answered = sum(r['incoming']['answered'] + r['outgoing']['answered'] for r in results)

        return Response({
            'start': start_str,
            'end': end_str,
            'total_calls': total_calls,
            'total_incoming': total_incoming,
            'total_outgoing': total_outgoing,
            'answer_rate': round(total_answered / total_calls * 100, 1) if total_calls else 0.0,
            'results': results,
        })


# ──────────────────────────────────────────────
# Client API: Top 10 Extensions by Call Count
# ──────────────────────────────────────────────

class ClientCDRTopExtensionsView(APIView):
    """
    POST /<tenant_uuid>/cdr/top-extensions/

    Body:
        {
            "start": "2026-04-01T00:00:00+05:30",
            "end":   "2026-04-06T23:59:59+05:30"
        }

    Returns top 10 extensions by total call count in the given range.
    """
    authentication_classes = [TenantAPIKeyAuthentication]
    permission_classes = [ClientAPIPermission]

    def get(self, request, tenant_uuid):
        tenant = _require_tenant(request, tenant_uuid, _tenant_from_request(request))

        start_str = (request.query_params.get('start') or '').strip()
        end_str = (request.query_params.get('end') or '').strip()

        if not start_str:
            raise ValidationError({'start': 'This field is required.'})
        if not end_str:
            raise ValidationError({'end': 'This field is required.'})

        try:
            utc_start = dp.parse(start_str).astimezone(pytz.utc)
        except Exception:
            raise ValidationError({'start': 'Invalid ISO datetime format.'})
        try:
            utc_end = dp.parse(end_str).astimezone(pytz.utc)
        except Exception:
            raise ValidationError({'end': 'Invalid ISO datetime format.'})

        if utc_start >= utc_end:
            raise ValidationError({'end': 'end must be after start.'})

        # Get all valid sip_usernames for this tenant with their display names
        ext_name_map = {
            e['sip_username']: e['effective_caller_id_name'] or e['outbound_caller_id_name'] or ''
            for e in Extension.objects.filter(tenant=tenant)
            .exclude(sip_username='')
            .values('sip_username', 'effective_caller_id_name', 'outbound_caller_id_name')
        }

        qs = (
            XmlCdr.objects
            .filter(tenant=tenant, start_stamp__gte=utc_start, start_stamp__lt=utc_end)
            .filter(extension_number__in=ext_name_map.keys())
            .values('extension_number')
            .annotate(total_calls=Count('xml_cdr_uuid'))
            .order_by('-total_calls')[:10]
        )

        results = [
            {
                'extension': row['extension_number'],
                'name': ext_name_map.get(row['extension_number'], ''),
                'calls': row['total_calls'],
            }
            for row in qs
        ]

        return Response({
            'start': start_str,
            'end': end_str,
            'results': results,
        })


# ──────────────────────────────────────────────
# Client API: Extension Inbound/Outbound Summary
# ──────────────────────────────────────────────

class ClientExtensionCallSummaryView(APIView):
    """
    POST /<tenant_uuid>/cdr/extension-call-summary/

    Body:
        {
            "extension": "901-IHS",
            "start": "2026-04-01T00:00:00+05:30",
            "end":   "2026-04-06T23:59:59+05:30"
        }

    Returns total inbound, outbound, and combined call counts for the extension.
    """
    authentication_classes = [TenantAPIKeyAuthentication]
    permission_classes = [ClientAPIPermission]

    def get(self, request, tenant_uuid):
        tenant = _require_tenant(request, tenant_uuid, _tenant_from_request(request))

        extension = request.query_params.get('extension', '').strip()
        start_str = request.query_params.get('start', '').strip()
        end_str = request.query_params.get('end', '').strip()

        if not extension:
            raise ValidationError({'extension': 'This field is required.'})
        if not start_str:
            raise ValidationError({'start': 'This field is required.'})
        if not end_str:
            raise ValidationError({'end': 'This field is required.'})

        try:
            utc_start = dp.parse(start_str).astimezone(pytz.utc)
        except Exception:
            raise ValidationError({'start': 'Invalid ISO datetime format.'})
        try:
            utc_end = dp.parse(end_str).astimezone(pytz.utc)
        except Exception:
            raise ValidationError({'end': 'Invalid ISO datetime format.'})

        if utc_start >= utc_end:
            raise ValidationError({'end': 'end must be after start.'})

        plain_ext = extension.split('-')[0]

        ext_obj = Extension.objects.filter(
            tenant=tenant,
        ).filter(
            Q(sip_username=extension) |
            Q(extension=plain_ext)
        ).first()
        ext_name = ext_obj.effective_caller_id_name if ext_obj else ''

        qs = XmlCdr.objects.filter(
            tenant=tenant,
            start_stamp__gte=utc_start,
            start_stamp__lt=utc_end,
            leg='a',
        ).filter(
            Q(extension_number=extension) |
            Q(extension_number=plain_ext) |
            Q(extension_number__startswith=f'{plain_ext}-')
        )

        _NO_ANSWER_CAUSES = (
            'NO_ANSWER', 'NO_USER_RESPONSE', 'SUBSCRIBER_ABSENT',
            'ALLOTTED_TIMEOUT', 'USER_NOT_REGISTERED', 'ORIGINATOR_CANCEL',
        )
        _FAILED_CAUSES = (
            'UNALLOCATED_NUMBER', 'NO_ROUTE_TRANSIT_NET', 'NO_ROUTE_DESTINATION',
            'CALL_REJECTED', 'NUMBER_CHANGED', 'DESTINATION_OUT_OF_ORDER',
            'INVALID_NUMBER_FORMAT', 'FACILITY_REJECTED', 'NETWORK_OUT_OF_ORDER',
            'TEMPORARY_FAILURE', 'CHANNEL_UNAVAILABLE', 'OUTGOING_CALL_BARRED',
            'INCOMING_CALL_BARRED', 'BEARER_NOT_AUTHORIZED', 'BEARER_NOT_AVAILABLE',
            'BEARER_NOT_IMPLEMENTED', 'FACILITY_NOT_IMPLEMENTED', 'SERVICE_NOT_IMPLEMENTED',
            'INVALID_CALL_REFERENCE', 'INCOMPATIBLE_DESTINATION', 'INTERWORKING',
            'CRASH', 'SYSTEM_SHUTDOWN', 'LOSE_RACE', 'MANAGER_REQUEST',
            'USER_CHALLENGE', 'MEDIA_TIMEOUT', 'PICKED_OFF', 'PROGRESS_TIMEOUT', 'GATEWAY_DOWN',
        )
        _CONGESTION_CAUSES = ('NORMAL_CIRCUIT_CONGESTION', 'SWITCH_CONGESTION', 'RESOURCE_UNAVAILABLE', 'SERVICE_UNAVAILABLE')
        _VOICEMAIL_Q = (
            Q(last_app='voicemail') |
            Q(last_app='speak', last_arg__contains='|') |
            Q(last_app='record', last_arg__contains='/voicemail/') |
            Q(last_app='system', last_arg__contains='voicemail-messages/ingest') |
            Q(last_app='phrase', last_arg__contains='voicemail')
        )
        _answered_Q = Q(hangup_cause__in=('NORMAL_CLEARING', 'CALL_AWARDED_DELIVERED'), billsec__gt=0) & ~_VOICEMAIL_Q
        _inbound_Q = Q(direction='inbound')
        _outbound_Q = Q(direction='outbound')

        agg = qs.aggregate(
            total_calls=Count('xml_cdr_uuid'),
            answered_calls=Count('xml_cdr_uuid', filter=_answered_Q),
            inbound_calls=Count('xml_cdr_uuid', filter=_inbound_Q),
            inbound_answered=Count('xml_cdr_uuid', filter=_inbound_Q & _answered_Q & ~_VOICEMAIL_Q),
            inbound_voicemail=Count('xml_cdr_uuid', filter=_inbound_Q & _VOICEMAIL_Q),
            inbound_missed=Count('xml_cdr_uuid', filter=_inbound_Q & Q(missed_call=True) & ~_VOICEMAIL_Q),
            inbound_no_answer=Count('xml_cdr_uuid', filter=_inbound_Q & Q(hangup_cause__in=_NO_ANSWER_CAUSES) & ~_VOICEMAIL_Q & Q(missed_call=False)),
            inbound_busy=Count('xml_cdr_uuid', filter=_inbound_Q & Q(hangup_cause='USER_BUSY') & ~_VOICEMAIL_Q),
            outbound_calls=Count('xml_cdr_uuid', filter=_outbound_Q),
            outbound_answered=Count('xml_cdr_uuid', filter=_outbound_Q & _answered_Q),
            outbound_no_answer=Count('xml_cdr_uuid', filter=_outbound_Q & Q(hangup_cause__in=_NO_ANSWER_CAUSES) & ~_answered_Q),
            outbound_busy=Count('xml_cdr_uuid', filter=_outbound_Q & Q(hangup_cause='USER_BUSY') & ~_answered_Q),
            outbound_congestion=Count('xml_cdr_uuid', filter=_outbound_Q & Q(hangup_cause__in=_CONGESTION_CAUSES) & ~_answered_Q),
            outbound_failed=Count('xml_cdr_uuid', filter=_outbound_Q & Q(hangup_cause__in=_FAILED_CAUSES) & ~_answered_Q & ~Q(hangup_cause__in=_NO_ANSWER_CAUSES) & ~Q(hangup_cause='USER_BUSY') & ~Q(hangup_cause__in=_CONGESTION_CAUSES)),
            total_duration=Sum('duration'),
            total_billsec=Sum('billsec'),
            avg_duration=Avg('duration'),
        )

        total = agg['total_calls'] or 0
        answered = agg['answered_calls'] or 0
        inbound = agg['inbound_calls'] or 0
        outbound = agg['outbound_calls'] or 0

        return Response({
            'extension': extension,
            'extension_name': ext_name,
            'start': start_str,
            'end': end_str,
            'total_calls': total,
            'total_duration': agg['total_duration'] or 0,
            'total_billsec': agg['total_billsec'] or 0,
            'avg_duration': round(agg['avg_duration'] or 0),
            'answer_rate': round(answered / total * 100, 1) if total else 0.0,
            'outgoing': {
                'total': outbound,
                'answered': agg['outbound_answered'] or 0,
                'no_answer': agg['outbound_no_answer'] or 0,
                'failed': agg['outbound_failed'] or 0,
                'congestion': agg['outbound_congestion'] or 0,
                'busy': agg['outbound_busy'] or 0,
            },
            'incoming': {
                'total': inbound,
                'answered': agg['inbound_answered'] or 0,
                'missed': agg['inbound_missed'] or 0,
                'no_answer': agg['inbound_no_answer'] or 0,
                'busy': agg['inbound_busy'] or 0,
                'voicemail': agg['inbound_voicemail'] or 0,
            },
        })


def _parse_utc_offset_minutes(offset_str):
    """
    Parse a UTC offset string into total minutes.
    Accepts: '+5', '-5', '-5.5', '+05:30', '-05:00', '6', etc.
    Also extracts offset from full ISO datetime strings like '2026-04-06T14:30:00-05:00'.
    """
    import re
    s = offset_str.strip()

    # Extract offset from full ISO datetime string e.g. '2026-04-06T14:30:00-05:00'
    iso_m = re.search(r'([+-])(\d{2}):(\d{2})$', s)
    if iso_m:
        sign = -1 if iso_m.group(1) == '-' else 1
        hours = int(iso_m.group(2))
        minutes = int(iso_m.group(3))
        return sign * (hours * 60 + minutes)

    # HH:MM format e.g. '+05:30', '-07:00'
    colon_m = re.fullmatch(r'([+-]?)(\d{1,2}):(\d{2})', s)
    if colon_m:
        sign = -1 if colon_m.group(1) == '-' else 1
        hours = int(colon_m.group(2))
        minutes = int(colon_m.group(3))
        return sign * (hours * 60 + minutes)

    # Plain numeric e.g. '+5', '-5.5', '6'
    num_m = re.fullmatch(r'([+-]?)(\d+(?:\.\d+)?)', s)
    if num_m:
        sign = -1 if num_m.group(1) == '-' else 1
        value = float(num_m.group(2))
        if value > 14:
            raise ValueError("utc_offset out of valid range (-14 to +14).")
        return sign * round(value * 60)

    raise ValueError("utc_offset must be a number like '-5', '+05:30', or an ISO datetime with offset.")


# ──────────────────────────────────────────────
# Stats Report: User Activity + DID Activity
# ──────────────────────────────────────────────

class StatsReportView(APIView):
    """
    GET /cdr/stats-report/?start=<ISO>&end=<ISO>

    Returns two sections:
      - user_activity: per-extension outbound/inbound breakdown
      - did_activity:  per-DID inbound breakdown
    """
    authentication_classes = [JWTAuthentication, SessionAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    _NO_ANSWER_CAUSES = (
        'NO_ANSWER', 'NO_USER_RESPONSE', 'SUBSCRIBER_ABSENT',
        'ALLOTTED_TIMEOUT', 'USER_NOT_REGISTERED', 'ORIGINATOR_CANCEL',
    )
    _FAILED_CAUSES = (
        'UNALLOCATED_NUMBER', 'NO_ROUTE_TRANSIT_NET', 'NO_ROUTE_DESTINATION',
        'CALL_REJECTED', 'NUMBER_CHANGED', 'DESTINATION_OUT_OF_ORDER',
        'INVALID_NUMBER_FORMAT', 'FACILITY_REJECTED', 'NETWORK_OUT_OF_ORDER',
        'TEMPORARY_FAILURE', 'CHANNEL_UNAVAILABLE', 'OUTGOING_CALL_BARRED',
        'INCOMING_CALL_BARRED', 'BEARER_NOT_AUTHORIZED', 'BEARER_NOT_AVAILABLE',
        'BEARER_NOT_IMPLEMENTED', 'FACILITY_NOT_IMPLEMENTED', 'SERVICE_NOT_IMPLEMENTED',
        'INVALID_CALL_REFERENCE', 'INCOMPATIBLE_DESTINATION', 'INTERWORKING',
        'CRASH', 'SYSTEM_SHUTDOWN', 'LOSE_RACE', 'MANAGER_REQUEST',
        'USER_CHALLENGE', 'MEDIA_TIMEOUT', 'PICKED_OFF', 'PROGRESS_TIMEOUT', 'GATEWAY_DOWN',
    )
    _CONGESTION_CAUSES = (
        'NORMAL_CIRCUIT_CONGESTION', 'SWITCH_CONGESTION',
        'RESOURCE_UNAVAILABLE', 'SERVICE_UNAVAILABLE',
    )
    _VOICEMAIL_Q = (
        Q(last_app='voicemail') |
        Q(last_app='speak', last_arg__contains='|') |
        Q(last_app='record', last_arg__contains='/voicemail/') |
        Q(last_app='system', last_arg__contains='voicemail-messages/ingest') |
        Q(last_app='phrase', last_arg__contains='voicemail')
    )

    def get(self, request):
        from apps.xml_cdr.models import XmlCdr
        from apps.extensions.models import Extension
        from apps.destinations.models import Destination
        from django.db.models import Sum, Count, Q

        tenant = getattr(request.user, 'tenant', None)
        if tenant is None:
            return Response({'error': 'No tenant associated with this user.'}, status=400)

        start_str = request.query_params.get('start', '').strip()
        end_str = request.query_params.get('end', '').strip()

        if not start_str:
            raise ValidationError({'start': 'This field is required.'})
        if not end_str:
            raise ValidationError({'end': 'This field is required.'})

        try:
            utc_start = dp.parse(start_str).astimezone(pytz.utc)
        except Exception:
            raise ValidationError({'start': 'Invalid ISO datetime format.'})
        try:
            utc_end = dp.parse(end_str).astimezone(pytz.utc)
        except Exception:
            raise ValidationError({'end': 'Invalid ISO datetime format.'})

        if utc_start >= utc_end:
            raise ValidationError({'end': 'end must be after start.'})

        _VM_Q = self._VOICEMAIL_Q
        _answered_Q = Q(hangup_cause__in=('NORMAL_CLEARING', 'CALL_AWARDED_DELIVERED'), billsec__gt=0) & ~_VM_Q
        _inbound_Q = Q(direction='inbound')
        _outbound_Q = Q(direction='outbound')
        _no_answer_Q = Q(hangup_cause__in=self._NO_ANSWER_CAUSES)
        _failed_Q = Q(hangup_cause__in=self._FAILED_CAUSES)
        _congestion_Q = Q(hangup_cause__in=self._CONGESTION_CAUSES)
        _busy_Q = Q(hangup_cause='USER_BUSY')

        base_qs = XmlCdr.objects.filter(
            tenant=tenant,
            start_stamp__gte=utc_start,
            start_stamp__lt=utc_end,
            leg='a',
        )
        ext_base_qs = XmlCdr.objects.filter(
            tenant=tenant,
            start_stamp__gte=utc_start,
            start_stamp__lt=utc_end,
        ).filter(
            Q(direction='outbound', leg='a') |
            Q(direction='inbound', leg='b') |
            (Q(direction='inbound', leg='a') & _VM_Q)
        )

        # ── Extension list (ALL extensions, including zero-call ones) ──────────
        ext_objs = list(
            Extension.objects.filter(tenant=tenant)
            .exclude(sip_username='')
            .values('sip_username', 'extension', 'effective_caller_id_name', 'outbound_caller_id_name')
        )
        # sip_username → display name
        ext_name_map = {
            e['sip_username']: (e['effective_caller_id_name'] or e['outbound_caller_id_name'] or '')
            for e in ext_objs
        }
        # plain extension number → display name (for lookup only)
        ext_num_map = {
            e['extension']: (e['effective_caller_id_name'] or e['outbound_caller_id_name'] or '')
            for e in ext_objs
        }
        known_sip_usernames = set(ext_name_map.keys())
        known_ext_numbers = set(ext_num_map.keys())
        known_extensions = known_sip_usernames | known_ext_numbers

        # ── Per-extension CDR aggregation ───────────────────────────────────
        ext_qs = (
            ext_base_qs
            .values('extension_number')
            .annotate(
                ob_answered=Count('xml_cdr_uuid', filter=_outbound_Q & _answered_Q),
                ob_busy=Count('xml_cdr_uuid', filter=_outbound_Q & _busy_Q & ~_answered_Q),
                ob_no_answer=Count('xml_cdr_uuid', filter=_outbound_Q & _no_answer_Q & ~_answered_Q),
                ob_failed=Count('xml_cdr_uuid', filter=_outbound_Q & _failed_Q & ~_answered_Q & ~_no_answer_Q & ~_busy_Q & ~_congestion_Q),
                ob_congestion=Count('xml_cdr_uuid', filter=_outbound_Q & _congestion_Q & ~_answered_Q),
                ob_total=Count('xml_cdr_uuid', filter=_outbound_Q),
                ob_talk_sec=Sum('billsec', filter=_outbound_Q & _answered_Q),
                ib_answered=Count('xml_cdr_uuid', filter=_inbound_Q & _answered_Q),
                ib_busy=Count('xml_cdr_uuid', filter=_inbound_Q & _busy_Q & ~_answered_Q),
                ib_no_answer=Count('xml_cdr_uuid', filter=_inbound_Q & _no_answer_Q & ~_answered_Q & ~_VM_Q),
                ib_failed=Count('xml_cdr_uuid', filter=_inbound_Q & _failed_Q & ~_answered_Q & ~_no_answer_Q & ~_busy_Q & ~_congestion_Q),
                ib_congestion=Count('xml_cdr_uuid', filter=_inbound_Q & _congestion_Q & ~_answered_Q),
                ib_voicemail=Count('xml_cdr_uuid', filter=_inbound_Q & _VM_Q),
                ib_total=Count('xml_cdr_uuid', filter=_inbound_Q),
                ib_talk_sec=Sum('billsec', filter=_inbound_Q & _answered_Q),
            )
        )

        _ZERO_ROW = {
            'ob_answered': 0, 'ob_busy': 0, 'ob_no_answer': 0, 'ob_failed': 0,
            'ob_congestion': 0, 'ob_total': 0, 'ob_talk_sec': 0,
            'ib_answered': 0, 'ib_busy': 0, 'ib_no_answer': 0, 'ib_failed': 0,
            'ib_congestion': 0, 'ib_voicemail': 0, 'ib_total': 0, 'ib_talk_sec': 0,
        }

        def _fmt_ext(ext_number, row, name=''):
            ob_talk = row['ob_talk_sec'] or 0
            ib_talk = row['ib_talk_sec'] or 0
            ob_ans  = row['ob_answered'] or 0
            ib_ans  = row['ib_answered'] or 0
            ob_total = row['ob_total'] or 0
            ib_total = row['ib_total'] or 0
            return {
                'extension': ext_number,
                'name': name,
                'outbound': {
                    'answered':   ob_ans,
                    'busy':       row['ob_busy'] or 0,
                    'no_answer':  row['ob_no_answer'] or 0,
                    'failed':     row['ob_failed'] or 0,
                    'congestion': row['ob_congestion'] or 0,
                    'total':      ob_total,
                    'talk_sec':   ob_talk,
                    'avg_talk_sec': round(ob_talk / ob_ans) if ob_ans else 0,
                },
                'inbound': {
                    'answered':   ib_ans,
                    'busy':       row['ib_busy'] or 0,
                    'no_answer':  row['ib_no_answer'] or 0,
                    'failed':     row['ib_failed'] or 0,
                    'congestion': row['ib_congestion'] or 0,
                    'voicemail':  row['ib_voicemail'] or 0,
                    'total':      ib_total,
                    'talk_sec':   ib_talk,
                    'avg_talk_sec': round(ib_talk / ib_ans) if ib_ans else 0,
                },
                'total_calls':    ob_total + ib_total,
                'total_talk_sec': ob_talk + ib_talk,
            }

        # Build a lookup of CDR rows keyed by extension_number
        cdr_by_ext = {}
        other_row = dict(_ZERO_ROW)
        has_other = False
        for row in ext_qs:
            ext_num = row['extension_number']
            if ext_num in known_extensions or any(ext_num.startswith(k + '-') for k in known_ext_numbers):
                # Normalise to plain extension number so we can merge sip_username variants
                plain = ext_num.split('-')[0]
                if plain in cdr_by_ext:
                    for k in _ZERO_ROW:
                        cdr_by_ext[plain][k] = (cdr_by_ext[plain].get(k) or 0) + (row.get(k) or 0)
                else:
                    cdr_by_ext[plain] = {k: row.get(k) or 0 for k in _ZERO_ROW}
            else:
                has_other = True
                for k in _ZERO_ROW:
                    other_row[k] = (other_row[k] or 0) + (row.get(k) or 0)

        # Build one row per known extension (zero-fill when no CDR data)
        known_rows = []
        seen_exts = set()
        for e in ext_objs:
            plain = e['extension']
            if plain in seen_exts:
                continue
            seen_exts.add(plain)
            name = e['effective_caller_id_name'] or e['outbound_caller_id_name'] or ''
            row_data = cdr_by_ext.get(plain, _ZERO_ROW)
            known_rows.append(_fmt_ext(plain, row_data, name))

        known_rows.sort(key=lambda r: r['extension'])

        if has_other:
            known_rows.append(_fmt_ext('Other', other_row, ''))

        # Totals row (excludes "Other" so it reflects registered extensions only + other)
        all_rows_for_total = known_rows
        totals = {
            'extension': 'TOTAL',
            'name': '',
            'outbound': {
                'answered':   sum(r['outbound']['answered']   for r in all_rows_for_total),
                'busy':       sum(r['outbound']['busy']       for r in all_rows_for_total),
                'no_answer':  sum(r['outbound']['no_answer']  for r in all_rows_for_total),
                'failed':     sum(r['outbound']['failed']     for r in all_rows_for_total),
                'congestion': sum(r['outbound']['congestion'] for r in all_rows_for_total),
                'total':      sum(r['outbound']['total']      for r in all_rows_for_total),
                'talk_sec':   sum(r['outbound']['talk_sec']   for r in all_rows_for_total),
                'avg_talk_sec': 0,
            },
            'inbound': {
                'answered':   sum(r['inbound']['answered']   for r in all_rows_for_total),
                'busy':       sum(r['inbound']['busy']       for r in all_rows_for_total),
                'no_answer':  sum(r['inbound']['no_answer']  for r in all_rows_for_total),
                'failed':     sum(r['inbound']['failed']     for r in all_rows_for_total),
                'congestion': sum(r['inbound']['congestion'] for r in all_rows_for_total),
                'voicemail':  sum(r['inbound']['voicemail']  for r in all_rows_for_total),
                'total':      sum(r['inbound']['total']      for r in all_rows_for_total),
                'talk_sec':   sum(r['inbound']['talk_sec']   for r in all_rows_for_total),
                'avg_talk_sec': 0,
            },
            'total_calls':    sum(r['total_calls']    for r in all_rows_for_total),
            'total_talk_sec': sum(r['total_talk_sec'] for r in all_rows_for_total),
        }
        ob_ans_total = totals['outbound']['answered']
        ib_ans_total = totals['inbound']['answered']
        if ob_ans_total:
            totals['outbound']['avg_talk_sec'] = round(totals['outbound']['talk_sec'] / ob_ans_total)
        if ib_ans_total:
            totals['inbound']['avg_talk_sec'] = round(totals['inbound']['talk_sec'] / ib_ans_total)

        # ── DID Activity (ALL registered DIDs, inbound + outbound) ─────────
        did_objs = list(
            Destination.objects.filter(tenant=tenant)
            .values('destination_number', 'destination_description')
        )
        did_label_map = {
            d['destination_number']: (d['destination_description'] or '')
            for d in did_objs
        }
        all_dids = set(did_label_map.keys())

        # Inbound stats keyed by destination_number
        ib_did_qs = (
            base_qs
            .filter(_inbound_Q)
            .values('destination_number')
            .annotate(
                ib_total=Count('xml_cdr_uuid'),
                ib_answered=Count('xml_cdr_uuid', filter=_answered_Q),
                ib_busy=Count('xml_cdr_uuid', filter=_busy_Q & ~_answered_Q),
                ib_no_answer=Count('xml_cdr_uuid', filter=_no_answer_Q & ~_answered_Q & ~_VM_Q),
                ib_failed=Count('xml_cdr_uuid', filter=_failed_Q & ~_answered_Q & ~_no_answer_Q & ~_busy_Q & ~_congestion_Q),
                ib_congestion=Count('xml_cdr_uuid', filter=_congestion_Q & ~_answered_Q),
                ib_talk_sec=Sum('billsec', filter=_answered_Q),
                ib_no_answer_sec=Sum('duration', filter=_no_answer_Q & ~_answered_Q),
            )
        )
        ib_by_did = {r['destination_number']: r for r in ib_did_qs}

        # Outbound stats keyed by caller_destination (the number dialled out via that DID)
        # FreeSWITCH stores the outbound gateway/DID in destination_number for outbound legs.
        ob_did_qs = (
            base_qs
            .filter(_outbound_Q)
            .filter(destination_number__in=all_dids)
            .values('destination_number')
            .annotate(
                ob_total=Count('xml_cdr_uuid'),
                ob_answered=Count('xml_cdr_uuid', filter=_answered_Q),
                ob_busy=Count('xml_cdr_uuid', filter=_busy_Q & ~_answered_Q),
                ob_no_answer=Count('xml_cdr_uuid', filter=_no_answer_Q & ~_answered_Q),
                ob_failed=Count('xml_cdr_uuid', filter=_failed_Q & ~_answered_Q & ~_no_answer_Q & ~_busy_Q & ~_congestion_Q),
                ob_congestion=Count('xml_cdr_uuid', filter=_congestion_Q & ~_answered_Q),
                ob_talk_sec=Sum('billsec', filter=_answered_Q),
            )
        )
        ob_by_did = {r['destination_number']: r for r in ob_did_qs}

        did_rows = []
        for did_num in sorted(all_dids):
            ib = ib_by_did.get(did_num, {})
            ob = ob_by_did.get(did_num, {})
            ib_ans  = ib.get('ib_answered') or 0
            ib_talk = ib.get('ib_talk_sec') or 0
            ob_ans  = ob.get('ob_answered') or 0
            ob_talk = ob.get('ob_talk_sec') or 0
            did_rows.append({
                'did':   did_num,
                'label': did_label_map.get(did_num, ''),
                'inbound': {
                    'total':      ib.get('ib_total') or 0,
                    'answered':   ib_ans,
                    'busy':       ib.get('ib_busy') or 0,
                    'no_answer':  ib.get('ib_no_answer') or 0,
                    'failed':     ib.get('ib_failed') or 0,
                    'congestion': ib.get('ib_congestion') or 0,
                    'talk_sec':   ib_talk,
                    'avg_talk_sec': round(ib_talk / ib_ans) if ib_ans else 0,
                    'no_answer_sec': ib.get('ib_no_answer_sec') or 0,
                },
                'outbound': {
                    'total':      ob.get('ob_total') or 0,
                    'answered':   ob_ans,
                    'busy':       ob.get('ob_busy') or 0,
                    'no_answer':  ob.get('ob_no_answer') or 0,
                    'failed':     ob.get('ob_failed') or 0,
                    'congestion': ob.get('ob_congestion') or 0,
                    'talk_sec':   ob_talk,
                    'avg_talk_sec': round(ob_talk / ob_ans) if ob_ans else 0,
                },
                'total_calls':    (ib.get('ib_total') or 0) + (ob.get('ob_total') or 0),
                'total_talk_sec': ib_talk + ob_talk,
            })

        did_totals = {
            'did': 'TOTAL',
            'label': '',
            'inbound': {
                'total':      sum(r['inbound']['total']      for r in did_rows),
                'answered':   sum(r['inbound']['answered']   for r in did_rows),
                'busy':       sum(r['inbound']['busy']       for r in did_rows),
                'no_answer':  sum(r['inbound']['no_answer']  for r in did_rows),
                'failed':     sum(r['inbound']['failed']     for r in did_rows),
                'congestion': sum(r['inbound']['congestion'] for r in did_rows),
                'talk_sec':   sum(r['inbound']['talk_sec']   for r in did_rows),
                'avg_talk_sec': 0,
                'no_answer_sec': sum(r['inbound']['no_answer_sec'] for r in did_rows),
            },
            'outbound': {
                'total':      sum(r['outbound']['total']      for r in did_rows),
                'answered':   sum(r['outbound']['answered']   for r in did_rows),
                'busy':       sum(r['outbound']['busy']       for r in did_rows),
                'no_answer':  sum(r['outbound']['no_answer']  for r in did_rows),
                'failed':     sum(r['outbound']['failed']     for r in did_rows),
                'congestion': sum(r['outbound']['congestion'] for r in did_rows),
                'talk_sec':   sum(r['outbound']['talk_sec']   for r in did_rows),
                'avg_talk_sec': 0,
            },
            'total_calls':    sum(r['total_calls']    for r in did_rows),
            'total_talk_sec': sum(r['total_talk_sec'] for r in did_rows),
        }
        ib_ans_t = did_totals['inbound']['answered']
        ob_ans_t = did_totals['outbound']['answered']
        if ib_ans_t:
            did_totals['inbound']['avg_talk_sec']  = round(did_totals['inbound']['talk_sec']  / ib_ans_t)
        if ob_ans_t:
            did_totals['outbound']['avg_talk_sec'] = round(did_totals['outbound']['talk_sec'] / ob_ans_t)

        return Response({
            'start': utc_start.isoformat(),
            'end':   utc_end.isoformat(),
            'user_activity': known_rows + [totals],
            'did_activity':  did_rows + [did_totals],
        })
