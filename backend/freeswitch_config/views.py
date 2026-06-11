"""
FreeSWITCH XML cURL handler.
FreeSWITCH sends POST requests here to get dynamic XML configuration.
Configure in FreeSWITCH: xml_curl.conf.xml -> gateway_url = http://localhost:8000/xml-curl/

CDR ingest:
FreeSWITCH mod_xml_cdr posts call records here after each call ends.
Configure in FreeSWITCH: xml_cdr.conf.xml -> url = http://localhost:8000/xml-curl/cdr/
"""
from django.http import HttpResponse
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.core.cache import cache
from .generators import (
    generate_directory_xml,
    generate_dialplan_xml,
    generate_configuration_xml,
    not_found_xml,
    _resolve_domain,
)
import logging

logger = logging.getLogger(__name__)


@method_decorator(csrf_exempt, name='dispatch')
class XmlCurlView(View):
    """Handles all XML cURL requests from FreeSWITCH."""

    def post(self, request, *args, **kwargs):
        section = request.POST.get('section', '')
        # FreeSWITCH sends hostname (e.g. "freeswitch") not the SIP domain for
        # dialplan requests. Use variable_domain_name (set from directory lookup)
        # as the authoritative domain, falling back to domain then hostname.
        domain = (
            request.POST.get('variable_domain_name', '')
            or request.POST.get('domain', '')
            or request.POST.get('hostname', '')
        )

        logger.info(
            f"XML cURL request: section={section} domain={domain} params={dict(request.POST)}"
        )

        try:
            if section == 'directory':
                user = request.POST.get('user', request.POST.get('user_name', ''))
                # Cache keyed by raw domain string from FreeSWITCH (e.g. "freeswitch" or "172.4.53.144").
                # Signals invalidate by canonical domain name — see signals.py _invalidate_directory_all().
                cache_key = f'directory:xml:{domain}:{user}' if user else f'directory:xml:{domain}'
                xml = cache.get(cache_key)
                if xml is None:
                    xml = generate_directory_xml(domain, user=user or None)
                    try:
                        cache.set(cache_key, xml, timeout=3600)
                    except Exception:
                        pass
                    logger.debug('Directory cache MISS domain=%s user=%s', domain, user)
                else:
                    logger.debug('Directory cache HIT domain=%s user=%s', domain, user)
            elif section == 'dialplan':
                destination = request.POST.get('Caller-Destination-Number', '')
                caller_id = request.POST.get('Caller-Caller-ID-Number', '')
                caller_name = request.POST.get('Caller-Caller-ID-Name', '')
                # FreeSWITCH only consumes the context it asked for. Scope the
                # generated dialplan to that context so the response stays well
                # under mod_xml_curl's ~1 MB cap (an unscoped multi-tenant
                # dialplan exceeds it and FreeSWITCH discards the whole reply).
                req_context = request.POST.get('Caller-Context', '')
                # Some profiles (e.g. webrtc) enter via a static context like
                # 'public', but authenticated calls actually route in the user's
                # per-tenant context (variable_user_context = default-<tenant>).
                # Keep BOTH so the call can reach tenant routing — otherwise
                # WebRTC/public-entry calls lose their extension/outbound routes.
                user_context = request.POST.get('variable_user_context', '')
                keep_contexts = [c for c in (req_context, user_context) if c]
                cache_key = f'dialplan:xml:{domain}:{":".join(keep_contexts)}'
                xml = cache.get(cache_key)
                if xml is None:
                    xml = generate_dialplan_xml(domain, destination, caller_id, caller_name,
                                                requested_context=keep_contexts)
                    try:
                        cache.set(cache_key, xml, timeout=3600)
                    except Exception:
                        pass  # Redis unavailable — serve uncached, don't crash
                    logger.debug('Dialplan cache MISS domain=%s', domain)
                else:
                    logger.debug('Dialplan cache HIT domain=%s', domain)
            elif section == 'configuration':
                # FreeSWITCH sends key_name='name' and key_value='voicemail.conf' etc.
                config_name = request.POST.get('key_value', '')
                # Only cache the high-frequency configs (ivr, voicemail, conference).
                # acl/callcenter/xml_cdr are loaded once at FS startup — not worth caching.
                _cacheable_configs = {'ivr.conf', 'voicemail.conf', 'conference.conf'}
                if config_name in _cacheable_configs:
                    cache_key = f'config:xml:{config_name}:{domain}'
                    xml = cache.get(cache_key)
                    if xml is None:
                        xml = generate_configuration_xml(config_name, domain)
                        try:
                            cache.set(cache_key, xml, timeout=3600)
                        except Exception:
                            pass
                        logger.debug('Config cache MISS config=%s domain=%s', config_name, domain)
                    else:
                        logger.debug('Config cache HIT config=%s domain=%s', config_name, domain)
                else:
                    xml = generate_configuration_xml(config_name, domain)
            elif section == 'phrases':
                xml = not_found_xml()
            else:
                xml = not_found_xml()
        except Exception as e:
            logger.error(f"XML cURL error: section={section} error={e}", exc_info=True)
            xml = not_found_xml()

        logger.debug(f"XML cURL response: section={section} domain={domain}\n{xml}")
        return HttpResponse(xml, content_type='text/xml; charset=utf-8')

    def get(self, request, *args, **kwargs):
        # Some FreeSWITCH versions send GET
        return self.post(request, *args, **kwargs)


from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions, status as drf_status


class CacheFlushView(APIView):
    """Flush all FreeSWITCH XML caches (dialplan, directory, config). Staff only."""
    permission_classes = [permissions.IsAdminUser]

    def post(self, request):
        try:
            cache.delete_pattern('dialplan:xml:*')
            cache.delete_pattern('directory:xml:*')
            cache.delete_pattern('config:xml:*')
        except Exception as e:
            return Response({'error': str(e)}, status=drf_status.HTTP_500_INTERNAL_SERVER_ERROR)
        return Response({'flushed': ['dialplan:xml:*', 'directory:xml:*', 'config:xml:*']})


def _process_cdr(var, int_var, stamp, call_uuid_fallback=None):
    """Shared CDR processing logic used by both XML and Lua CDR ingest views."""
    from apps.xml_cdr.models import XmlCdr

    domain_name = var('domain_name') or var('variable_domain_name') or var('sip_to_host')
    domain = _resolve_domain(domain_name) if domain_name else None
    # Do not derive tenant from domain — a shared/universal domain belongs to
    # one tenant but is used by all. Resolve tenant from call variables instead.
    tenant = None

    if tenant is None:
        from core.models import Tenant
        tenant_code = None
        context_val = var('context', '')
        if context_val.startswith('default-'):
            tenant_code = context_val[len('default-'):]
        else:
            # username (e.g. 100-SIS) is the most reliable source — check it first,
            # then fall back to the dialed extension fields (e.g. 901-IHDT on a
            # gateway-bound B-leg), sip_from_user and caller_id_number.
            for field in (var('username'), var('sip_from_user'),
                          var('dialed_extension'), var('sip_to_user'),
                          var('sip_req_user'), var('destination_number'),
                          var('caller_id_number')):
                if field and '-' in field:
                    tenant_code = field.rsplit('-', 1)[-1]
                    break
        if tenant_code:
            try:
                tenant = Tenant.objects.get(tenant_code=tenant_code)
                if domain is None:
                    domain = tenant.domains.filter(domain_enabled=True).first()
            except Tenant.DoesNotExist:
                pass

    if tenant is None:
        from apps.destinations.models import Destination

        def _normalize_candidates(number):
            if not number:
                return []
            candidates = [number]
            if number.startswith('+1'):
                candidates.append(number[2:])
                candidates.append(number[1:])
            elif number.startswith('1') and len(number) == 11:
                candidates.append('+' + number)
                candidates.append(number[1:])
            else:
                candidates.append('+1' + number)
            return candidates

        dest = var('destination_number') or var('sip_req_user') or var('sip_to_user')
        src = var('caller_id_number') or var('effective_caller_id_number')
        for number in (dest, src):
            for candidate in _normalize_candidates(number):
                did = Destination.objects.filter(destination_number=candidate).select_related('tenant').first()
                if did and did.tenant:
                    tenant = did.tenant
                    if domain is None:
                        domain = tenant.domains.filter(domain_enabled=True).first()
                    break
            if tenant:
                break

    if tenant is None:
        # Inherit the tenant from the A-leg. Prefer originating_leg_uuid/originator,
        # but fall back to bridge_uuid/signal_bond so B-legs (e.g. gateway-bound
        # legs) still resolve when no originating_leg_uuid was set on this leg.
        for originating_uuid in (var('originating_leg_uuid'), var('originator'),
                                 var('bridge_uuid'), var('signal_bond')):
            if not originating_uuid:
                continue
            a_leg = XmlCdr.objects.filter(call_uuid=originating_uuid).select_related('tenant', 'domain').first()
            if a_leg and a_leg.tenant:
                tenant = a_leg.tenant
                if domain is None:
                    domain = a_leg.domain
                break

    if domain is None:
        logger.warning(f"CDR ingest: could not resolve domain from domain_name={domain_name!r}")

    raw_direction = var('direction', 'inbound')
    context_val = var('context', '')
    caller_number = var('caller_id_number') or var('effective_caller_id_number') or var('sip_from_user') or ''
    last_app_val = var('last_app', '').lower()
    last_arg_val = var('last_arg', '')
    originating_leg_uuid = var('originating_leg_uuid') or var('originator') or ''
    is_originating_leg = bool(originating_leg_uuid)
    bridged_to_gateway = last_app_val == 'bridge' and 'sofia/gateway/' in last_arg_val
    # For inheriting the A-leg's direction we also accept bridge_uuid/signal_bond:
    # a gateway-bound B-leg often carries no originating_leg_uuid but its
    # bridge_uuid points back at the A-leg. This is used ONLY for direction —
    # not for leg/dedup, which must stay keyed on the true originating fields.
    a_leg_ref = (originating_leg_uuid or var('bridge_uuid')
                 or var('signal_bond') or '')
    originating_leg_direction = None
    if a_leg_ref:
        try:
            origin_leg = XmlCdr.objects.filter(call_uuid=a_leg_ref, leg='a').only('direction').first()
            if origin_leg:
                originating_leg_direction = origin_leg.direction
        except Exception:
            originating_leg_direction = None

    # Most reliable signal: an internal extension placing a call to a PSTN/E.164
    # number is outbound, no matter what FreeSWITCH's raw_direction says on a
    # gateway leg. Caller is an extension (short digits, optional -TENANT suffix);
    # destination is a long (>=7 digit) external number.
    _caller_head = caller_number.split('-', 1)[0].lstrip('+')
    # A real internal extension is 2-5 digits and not an all-zero/service stub.
    caller_is_ext = (_caller_head.isdigit() and 2 <= len(_caller_head) <= 5
                     and _caller_head.strip('0') != '')
    _dest = (var('destination_number') or var('sip_req_user')
             or var('sip_to_user') or '').lstrip('+')
    # Destination is a NANP PSTN number (10 digits, or 11 starting with 1).
    dest_is_pstn = _dest.isdigit() and (len(_dest) == 10
                                        or (len(_dest) == 11 and _dest[0] == '1'))

    if caller_is_ext and dest_is_pstn:
        direction = 'outbound'
    elif bridged_to_gateway:
        direction = 'outbound'
    elif originating_leg_direction in ('inbound', 'outbound'):
        # Inherit from the A-leg (found via originating_leg_uuid OR bridge_uuid).
        direction = originating_leg_direction
    elif is_originating_leg:
        caller_digits = caller_number.lstrip('+')
        direction = 'outbound' if len(caller_digits) <= 6 else 'inbound'
    elif context_val == 'public':
        direction = 'outbound' if len(caller_number.lstrip('+')) <= 6 else 'inbound'
    elif context_val.startswith('default-'):
        # default- context is used for both inbound (DID routed to extension) and
        # outbound (extension dialing out). Trust FreeSWITCH raw_direction here.
        direction = raw_direction if raw_direction in ('inbound', 'outbound') else 'inbound'
    else:
        direction = raw_direction if raw_direction in ('inbound', 'outbound', 'local') else 'inbound'

    duration = int_var('duration')
    waitsec = int_var('waitsec')
    answer_epoch = int_var('answer_epoch')
    end_epoch = int_var('end_epoch')
    raw_billsec = int_var('billsec')
    # Missed/offline calls have no talk time regardless of what FreeSWITCH reports.
    hangup_cause_raw = var('hangup_cause', '')
    if hangup_cause_raw == 'USER_NOT_REGISTERED':
        billsec = 0
    elif answer_epoch > 0 and end_epoch > 0:
        billsec = max(0, end_epoch - answer_epoch)
    else:
        billsec = raw_billsec
    leg = 'b' if is_originating_leg else 'a'
    # Note: prefer var('username') (the actual sip user on this leg). Only fall
    # back to sip_from_user for outbound, where it's the dialing extension.
    # Falling back to sip_from_user on inbound legs would mistake the PSTN
    # caller for the extension.
    sip_username_raw = var('username') or ''
    sip_from_user = var('sip_from_user') or ''
    sip_to_user = var('sip_to_user') or var('sip_req_user') or ''

    def _looks_like_internal_ext(val: str) -> bool:
        """Real internal extensions are short digit strings, optionally suffixed
        with -TENANTCODE (e.g. '901', '901-IHDT'). PSTN numbers, E.164, and
        SIP transfer IDs (o7mvb2pc) all fail this check."""
        if not val:
            return False
        head = val.split('-', 1)[0]
        return head.isdigit() and 1 <= len(head) <= 6

    # Authoritative signal: the dialplan exports ihs_dialed_ext (the suffixed
    # sip_username, e.g. "901-IHDT") onto every leg of an inbound call to an
    # extension — including bridge B-legs and immediate USER_BUSY/NO_ANSWER legs
    # whose destination_number is only a WebRTC session token. When present it
    # wins over every heuristic below. See generators.py ext_*_bridge/_offline.
    ihs_dialed_ext = var('ihs_dialed_ext')

    if direction == 'outbound':
        # Outbound A-leg: the dialing extension is sip_from_user.
        extension_number = sip_username_raw or sip_from_user
    elif ihs_dialed_ext:
        extension_number = ihs_dialed_ext
    else:
        # For B-legs of inbound calls (forked ring group dial), each B-leg's
        # `username` is the SIP username of the specific device that rang —
        # this uniquely identifies each fork target.
        if leg == 'b' and _looks_like_internal_ext(sip_username_raw):
            extension_number = sip_username_raw
        else:
            extension_number = var('dialed_extension') or ''
            if not extension_number:
                bridge_channel = var('bridge_channel') or var('variable_bridge_channel') or ''
                # extract the user part from sofia/internal/sip:USER@host or sofia/internal/USER@host
                import re as _re
                m = _re.search(r'sip:([^@;]+)@|/([^/@;]+)@', bridge_channel)
                if m:
                    extension_number = m.group(1) or m.group(2)
            # WebRTC bridge B-legs carry a SIP token (e.g. "n0kj384g") in every
            # destination field, but the real dialed extension survives in
            # transfer_source / transfer_history as "...:bl_xfer:202/default-IHDT/XML".
            # That is the most reliable place to recover it.
            if not _looks_like_internal_ext(extension_number):
                xfer = var('transfer_source') or var('transfer_history')
                if xfer:
                    import re as _re2
                    m2 = _re2.search(r'bl_xfer:(\d{1,6})/', xfer)
                    if m2:
                        extension_number = m2.group(1)
            # Final fallback: sip_to_user — but only if it looks like a real ext.
            # Never let PSTN numbers (+13465711217) or random SIP IDs end up in
            # extension_number; leave it blank instead.
            if not extension_number and _looks_like_internal_ext(sip_to_user):
                extension_number = sip_to_user
            if not _looks_like_internal_ext(extension_number):
                extension_number = ''
    # Normalize to sip_username format (e.g. "901-IHS") so inbound and outbound are consistent.
    # Look up by plain extension number if extension_number doesn't already contain a dash.
    if extension_number and '-' not in extension_number and tenant:
        try:
            from apps.extensions.models import Extension as ExtModel
            ext_obj = (
                ExtModel.objects.filter(tenant=tenant, extension=extension_number).first()
                or ExtModel.objects.filter(tenant=tenant, sip_username=extension_number).first()
            )
            if ext_obj and ext_obj.sip_username:
                extension_number = ext_obj.sip_username
        except Exception:
            pass

    # Last-resort tenant recovery from the resolved extension_number. It is
    # computed above from dialed_extension / bridge_channel / sip_to_user — fields
    # the early suffix scan does not all see — so a leg whose only tenant signal is
    # a suffixed dialed extension (e.g. "1003-IHDT") still resolves here instead of
    # landing tenant=NULL and disappearing from every tenant-scoped call log.
    if tenant is None and extension_number and '-' in extension_number:
        from core.models import Tenant
        candidate_code = extension_number.rsplit('-', 1)[-1]
        try:
            tenant = Tenant.objects.get(tenant_code=candidate_code)
            if domain is None:
                domain = tenant.domains.filter(domain_enabled=True).first()
            logger.info("CDR ingest: recovered tenant %s from extension_number %r",
                        candidate_code, extension_number)
        except Tenant.DoesNotExist:
            pass

    # Last-resort tenant recovery via DID match on the DIALED destination only.
    # IMPORTANT: match the destination (the number that was CALLED), never the
    # caller_id_number. A caller's CID can coincidentally equal some other
    # tenant's DID — e.g. an external party calling IHDT's DID while presenting
    # an IHS DID as caller-id — and matching the caller would mis-attribute the
    # whole call to the wrong tenant. Only the dialed DID identifies the owner.
    if tenant is None:
        from apps.destinations.models import Destination

        def _did_candidates(number):
            if not number:
                return []
            cands = [number]
            if number.startswith('+1'):
                cands += [number[2:], number[1:]]
            elif number.startswith('1') and len(number) == 11:
                cands += ['+' + number, number[1:]]
            else:
                cands.append('+1' + number)
            return cands

        # rdnis = the original DID for a call that was transferred/forwarded to a
        # token destination (WebRTC bridge leg); sip_req_user/sip_to_user carry
        # the DID on the raw inbound leg. destination_number last (it is often a
        # SIP session token on bridged legs). Never the caller.
        for number in (var('rdnis'), var('sip_req_user'), var('sip_to_user'),
                       var('destination_number')):
            matched = False
            for candidate in _did_candidates(number):
                did = Destination.objects.filter(destination_number=candidate).select_related('tenant').first()
                if did and did.tenant:
                    tenant = did.tenant
                    if domain is None:
                        domain = tenant.domains.filter(domain_enabled=True).first()
                    logger.info("CDR ingest: recovered tenant %s via dialed DID %r",
                                tenant.tenant_code, candidate)
                    matched = True
                    break
            if matched:
                break

    call_uuid_val = call_uuid_fallback or var('uuid') or var('call_uuid') or None
    cdr_fields = dict(
        domain=domain,
        tenant=tenant,
        caller_id_name=var('caller_id_name') or var('effective_caller_id_name') or var('sip_from_display') or var('sip_from_user'),
        caller_id_number=var('caller_id_number') or var('effective_caller_id_number') or var('sip_from_user'),
        extension_number=extension_number,
        caller_destination=var('caller_destination') or var('sip_req_user'),
        destination_number=var('destination_number') or var('sip_req_user') or var('sip_to_user'),
        context=var('context'),
        start_epoch=int_var('start_epoch'),
        start_stamp=stamp('start_stamp'),
        answer_epoch=answer_epoch,
        answer_stamp=stamp('answer_stamp'),
        end_epoch=end_epoch,
        end_stamp=stamp('end_stamp'),
        duration=duration,
        mduration=int_var('mduration'),
        billsec=billsec,
        billmsec=int_var('billmsec'),
        read_codec=var('read_codec'),
        read_rate=var('read_rate'),
        write_codec=var('write_codec'),
        write_rate=var('write_rate'),
        remote_media_ip=var('remote_media_ip'),
        network_addr=var('network_addr'),
        last_app=var('last_app'),
        # Truncate to the column width (1024). Voicemail legs carry the full
        # record-stop curl in last_arg (~400+ chars); an over-length value made
        # the ENTIRE row insert fail, so the call was lost / left as a stale
        # synthetic USER_BUSY row instead of being classified as voicemail.
        last_arg=var('last_arg')[:1024],
        hangup_cause=hangup_cause_raw,
        hangup_cause_q850=int_var('hangup_cause_q850'),
        direction=direction,
        missed_call=(
            direction != 'outbound'
            and (billsec == 0 or var('hangup_cause') == 'USER_NOT_REGISTERED')
            and last_app_val != 'voicemail'
            and not (last_app_val == 'speak' and '|' in last_arg_val)
            and not (last_app_val == 'record' and '/voicemail/' in last_arg_val)
            and not (last_app_val == 'system' and 'voicemail-messages/ingest' in last_arg_val)
            and not (last_app_val == 'phrase' and 'voicemail' in last_arg_val)
        ),
        bypass_media=(var('bypass_media') == 'true' or var('proxy_media') == 'true'),
        call_uuid=call_uuid_val,
        leg=leg,
        bridge_uuid=var('bridge_uuid') or var('signal_bond') or originating_leg_uuid or None,
        pdd_ms=int_var('progress_mediamsec') or int_var('pdd_ms'),
        waitsec=waitsec,
        cc_queue=var('cc_queue'),
        cc_agent=var('cc_agent'),
        record_path=var('record_path') or var('record_file_path'),
        record_name=var('record_name') or var('record_file_name'),
    )

    try:
        # For A-legs: use update_or_create keyed on call_uuid+leg so that when the real A-leg CDR
        # arrives after a synthetic A-leg was already created (B-legs posted first), the synthetic
        # is overwritten rather than leaving a duplicate record.
        if leg == 'a' and call_uuid_val:
            record, created = XmlCdr.objects.update_or_create(
                call_uuid=call_uuid_val, leg='a',
                defaults=cdr_fields,
            )
            logger.info(
                f"CDR ingest: {'created' if created else 'updated'} A-leg "
                f"{record.caller_id_number} -> {record.destination_number} "
                f"({record.billsec}s, {record.hangup_cause})"
            )
        else:
            record = XmlCdr.objects.create(**cdr_fields)
            logger.info(
                f"CDR ingest: saved {record.caller_id_number} -> {record.destination_number} "
                f"({record.billsec}s, {record.hangup_cause})"
            )

        # If this is a B-leg and no A-leg exists for this call, create a synthetic A-leg.
        # FreeSWITCH sometimes only posts the B-leg for voicemail flows where the
        # inbound channel CDR is not sent (e.g. transferred calls where context changes).
        # A B-leg only warrants a synthetic A-leg if it carries enough routing
        # data to stand in for the real inbound leg. FreeSWITCH's voicemail
        # `record` application spawns internal media pseudo-legs whose
        # destination_number is a session token (e.g. 'vqsairma'), with empty
        # context/last_app and no resolvable tenant. Those carry nothing useful —
        # synthesizing an A-leg from them produces a tenant=None / last_app=''
        # row that the (call_uuid, leg='a') unique constraint then lets clobber a
        # real A-leg, hiding the call from the tenant-scoped call logs. Skip them.
        b_leg_is_routable = bool(record.tenant_id or record.context or last_app_val)
        if leg == 'b' and record.bridge_uuid and b_leg_is_routable:
            # For ring groups (simultaneous), each B-leg may have a different bridge_uuid but all
            # share the same originating_leg_uuid pointing to the A-leg. Use originating_leg_uuid
            # as the primary check to avoid creating duplicate synthetic A-legs.
            a_leg_uuid = originating_leg_uuid or str(record.bridge_uuid)
            a_leg_exists = XmlCdr.objects.filter(call_uuid=a_leg_uuid, leg='a').exists()
            if not a_leg_exists:
                try:
                    syn_defaults = dict(
                        domain=record.domain,
                        tenant=record.tenant,
                        caller_id_name=record.caller_id_name,
                        caller_id_number=record.caller_id_number,
                        extension_number=record.extension_number,
                        caller_destination=record.caller_destination,
                        destination_number=record.destination_number,
                        context=record.context,
                        start_epoch=record.start_epoch,
                        start_stamp=record.start_stamp,
                        answer_epoch=record.answer_epoch,
                        answer_stamp=record.answer_stamp,
                        end_epoch=record.end_epoch,
                        end_stamp=record.end_stamp,
                        duration=record.duration,
                        mduration=record.mduration,
                        billsec=record.billsec,
                        billmsec=record.billmsec,
                        read_codec=record.read_codec,
                        read_rate=record.read_rate,
                        write_codec=record.write_codec,
                        write_rate=record.write_rate,
                        remote_media_ip=record.remote_media_ip,
                        network_addr=record.network_addr,
                        last_app=record.last_app,
                        last_arg=record.last_arg,
                        hangup_cause=record.hangup_cause,
                        hangup_cause_q850=record.hangup_cause_q850,
                        direction='inbound',
                        missed_call=record.missed_call,
                        bypass_media=record.bypass_media,
                        bridge_uuid=record.call_uuid,
                        pdd_ms=record.pdd_ms,
                        waitsec=record.waitsec,
                        cc_queue=record.cc_queue,
                        cc_agent=record.cc_agent,
                        record_path=record.record_path,
                        record_name=record.record_name,
                    )
                    # IMPORTANT: get_or_create, NOT update_or_create. A synthetic
                    # A-leg is a best-effort stand-in built from a B-leg's fields
                    # (often a transfer/gateway leg with tenant=None and a SIP
                    # transfer pseudo-extension like 'vqsairma' as destination).
                    # It must NEVER overwrite a real A-leg: the (call_uuid, leg='a')
                    # unique constraint means there is exactly one A-leg row, and
                    # the real A-leg — written via update_or_create on line ~410 —
                    # is always authoritative. Using update_or_create here let a
                    # late-arriving garbage B-leg clobber a good real A-leg,
                    # blanking tenant/last_app and hiding the call from call logs.
                    _, syn_created = XmlCdr.objects.get_or_create(
                        call_uuid=a_leg_uuid, leg='a',
                        defaults=syn_defaults,
                    )
                    logger.info(
                        f"CDR ingest: {'created synthetic A-leg' if syn_created else 'kept existing A-leg'} for orphaned B-leg "
                        f"{record.caller_id_number} -> {record.destination_number} bridge_uuid={record.bridge_uuid}"
                    )
                except Exception as syn_exc:
                    logger.warning(f"CDR ingest: failed to create synthetic A-leg: {syn_exc}")

    except Exception as e:
        logger.error(f"CDR ingest: failed to save record: {e}", exc_info=True)

    if var('last_app', '').lower() == 'txfax':
        call_uuid = call_uuid_fallback or var('uuid') or var('call_uuid') or ''
        fax_success = var('fax_success', '')
        fax_pages = var('fax_document_transferred_pages', '0')
        if call_uuid:
            try:
                from apps.fax.models import FaxFile
                ff = FaxFile.objects.filter(channel_uuid=call_uuid, fax_file_status='pending').first()
                if ff:
                    new_status = 'sent' if fax_success == '1' else 'failed'
                    update_fields = ['fax_file_status']
                    ff.fax_file_status = new_status
                    try:
                        pages = int(fax_pages)
                        if pages > 0:
                            ff.fax_file_pages = pages
                            update_fields.append('fax_file_pages')
                    except (ValueError, TypeError):
                        pass
                    ff.save(update_fields=update_fields)
                    logger.info(f"CDR ingest: updated FaxFile {ff.fax_file_uuid} → {new_status}")

                    if ff.tenant_id:
                        try:
                            from apps.client_api.tasks import fire_webhook_event
                            event = 'fax.sent' if new_status == 'sent' else 'fax.failed'
                            fire_webhook_event.delay(
                                str(ff.tenant_id), event, str(ff.fax_file_uuid),
                                inline_data={
                                    'direction': 'outbound',
                                    'fax_file_uuid': str(ff.fax_file_uuid),
                                    'fax_uuid': str(ff.fax.fax_uuid) if ff.fax_id else None,
                                    'status': new_status,
                                    'pages': ff.fax_file_pages,
                                    'file_size_bytes': ff.file_size_bytes,
                                    'caller_id_number': ff.fax_file_caller_id_number,
                                    'destination_number': ff.fax_file_destination_number,
                                },
                            )
                        except Exception as wh_exc:
                            logger.error(f"CDR ingest: failed to fire fax webhook: {wh_exc}")
            except Exception as e:
                logger.error(f"CDR ingest: failed to update FaxFile: {e}")

    return HttpResponse('OK')


@method_decorator(csrf_exempt, name='dispatch')
class CdrIngestView(View):
    """
    Receives XML CDR posts from FreeSWITCH mod_xml_cdr after each call ends.

    FreeSWITCH posts the CDR as a URL-encoded 'cdr' parameter containing an
    XML document. This view parses it and saves a record to v_xml_cdr.

    FreeSWITCH config (xml_cdr.conf.xml):
        <param name="url" value="http://<django-host>/xml-curl/cdr/"/>
        <param name="encode" value="true"/>
        <param name="retries" value="2"/>
        <param name="delay" value="5"/>
    """

    def post(self, request, *args, **kwargs):
        from lxml import etree
        from apps.xml_cdr.models import XmlCdr
        from django.utils.dateparse import parse_datetime

        cdr_xml = request.POST.get('cdr', '')
        if not cdr_xml:
            # FreeSWITCH sometimes posts raw XML body instead of form-encoded
            cdr_xml = request.body.decode('utf-8', errors='replace').strip()
        if not cdr_xml:
            logger.warning(f"CDR ingest: received empty POST body — POST keys: {list(request.POST.keys())} body_len={len(request.body)}")
            return HttpResponse('OK')

        logger.debug(f"CDR ingest raw (len={len(cdr_xml)}): {cdr_xml[:200]}")

        # JSON CDR (mod_json_cdr) — parse variables and process same as XML CDR
        if cdr_xml.lstrip().startswith('{'):
            import json
            try:
                cdr_json = json.loads(cdr_xml)
            except json.JSONDecodeError:
                # mod_json_cdr embeds literal \r\n bytes in SDP fields — replace with space and retry
                sanitized = cdr_xml.replace('\r\n', ' ').replace('\r', ' ').replace('\n', ' ')
                try:
                    cdr_json = json.loads(sanitized)
                except Exception as e:
                    logger.error(f"CDR ingest: failed to parse JSON CDR: {e}")
                    return HttpResponse('OK')
            variables = cdr_json.get('variables', {})

            def var(name, default=''):
                return str(variables.get(name, default)) if variables.get(name) is not None else default

            def int_var(name):
                try:
                    return int(var(name, '0'))
                except ValueError:
                    return 0

            def stamp(name):
                raw = var(name)
                if not raw:
                    return None
                try:
                    from django.utils.dateparse import parse_datetime
                    return parse_datetime(raw.replace(' ', 'T'))
                except Exception:
                    return None

            call_uuid = variables.get('uuid') or cdr_json.get('uuid')
            return _process_cdr(var, int_var, stamp, call_uuid_fallback=call_uuid)

        # Strip XML declaration if present — lxml can't parse unicode strings with it
        if cdr_xml.startswith('<?xml'):
            cdr_xml = cdr_xml[cdr_xml.index('?>') + 2:].strip()

        # Remove any variable elements with colons in tag names (e.g. nolocal:foo)
        # which lxml rejects as invalid namespace prefixes.
        import re
        cdr_xml = re.sub(r'<(/?)([a-zA-Z_][\w.-]*:[a-zA-Z_][\w.-]*)[^>]*>', '', cdr_xml)

        try:
            root = etree.fromstring(cdr_xml.encode())
        except Exception as e:
            logger.error(f"CDR ingest: failed to parse XML: {e}")
            return HttpResponse('OK')

        def var(name, default=''):
            from urllib.parse import unquote
            el = root.find(f'.//variables/{name}')
            if el is not None and el.text:
                return unquote(el.text.strip())
            # Fallback: several routing/tenant fields (context, rdnis,
            # destination_number, username) live in <callflow><caller_profile>
            # but NOT in <variables> — notably on WebRTC bridge B-legs whose
            # <variables> carry only the session token. The most recent callflow
            # (profile_index highest, i.e. last in document order) reflects the
            # final routing state. Read from the last caller_profile.
            if name in ('context', 'rdnis', 'destination_number', 'username',
                        'caller_id_number', 'caller_id_name', 'network_addr',
                        'dialed_extension'):
                profiles = root.findall('.//callflow/caller_profile')
                for prof in reversed(profiles):
                    cel = prof.find(name)
                    if cel is not None and cel.text and cel.text.strip():
                        return unquote(cel.text.strip())
            return default

        def int_var(name):
            try:
                return int(var(name, '0'))
            except ValueError:
                return 0

        def stamp(name):
            raw = var(name)
            if not raw:
                return None
            try:
                return parse_datetime(raw.replace(' ', 'T'))
            except Exception:
                return None

        return _process_cdr(var, int_var, stamp, call_uuid_fallback=var('uuid') or root.findtext('.//callflow/caller_profile/uuid'))

    def get(self, request, *args, **kwargs):
        return HttpResponse('CDR ingest endpoint — POST only', status=405)


