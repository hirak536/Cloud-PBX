"""
XML generators for FreeSWITCH XML cURL backend.
FreeSWITCH calls these endpoints to get dynamic configuration.
Each function returns an XML string for the relevant section.
"""
from django.db import models
from django.conf import settings
from lxml import etree
import logging
import re
from datetime import datetime
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)


def not_found_xml():
    """Standard FreeSWITCH not-found response."""
    return '''<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<document type="freeswitch/xml">
  <section name="result">
    <result status="not found" />
  </section>
</document>'''


def _add_recording_actions(cond, domain_name):
    """
    Add FreeSWITCH recording actions to a dialplan condition.
    Must be executed BEFORE bridge.
    """

    record_path = (
        '${recordings_dir}/${domain_name}/'
        '${strftime(%Y-%m-%d-%H-%M-%S)}_'
        '${caller_id_number}_'
        '${destination_number}_'
        '${uuid}.wav'
    )

    ingest_url = (
        'http://127.0.0.1:8000/api/v1/recordings/call-recordings/ingest/'
        '?file=${record_file}'
        '&caller=${caller_id_number}'
        '&caller_name=${caller_id_name}'
        '&destination=${destination_number}'
        '&domain=${domain_name}'
        '&duration=${duration}'
        '&billsec=${billsec}'
    )

    etree.SubElement(cond, 'action', application='set', data='RECORD_STEREO=true')
    etree.SubElement(cond, 'action', application='set', data='recording_follow_transfer=true')
    etree.SubElement(cond, 'action', application='set', data='media_bug_answer_req=true')
    etree.SubElement(cond, 'action', application='set', data=f'record_file={record_path}', inline='true')

    # Ensure recording directory exists on disk
    etree.SubElement(cond, 'action', application='system', data='mkdir -p ${recordings_dir}/${domain_name}')

    # Properly quote the ingest URL and use system:curl for reliable delivery
    etree.SubElement(cond, 'action', application='set',
                     data=f'api_hangup_hook=system curl -k "{ingest_url}"')

    # Prevent multiple recording starts on the same call leg (e.g. DID context -> Extension context)
    # Use eval + cond to start record_session only if the recording_started flag is not set.
    etree.SubElement(cond, 'action', application='eval',
                     data='${cond(${recording_started} == "true" ? "already_recording" : ${set(recording_started=true)}${record_session(${record_file})})}')


def _resolve_domain(domain_name):
    """Look up a Domain by name, falling back to domain alias settings."""
    from core.models import Domain, DomainSetting
    try:
        return Domain.objects.get(domain_name=domain_name, domain_enabled=True)
    except Domain.DoesNotExist:
        pass
    # Fall back to domain alias: a DomainSetting with category='domain',
    # subcategory='alias', value=<alias_name> maps an IP or alternate name
    # to an existing domain (same storage pattern as original FusionPBX).
    setting = DomainSetting.objects.select_related('domain').filter(
        domain_setting_category='domain',
        domain_setting_subcategory='alias',
        domain_setting_name='text',
        domain_setting_value=domain_name,
        domain_setting_enabled=True,
        domain__domain_enabled=True,
    ).first()
    if setting:
        return setting.domain

    # If no match found and domain_name looks like an IP, check for universal or single-tenant fallback.
    if re.match(r'^\d+\.\d+\.\d+\.\d+$', domain_name):
        # 1. Try universal domain
        universal = Domain.objects.filter(domain_universal=True, domain_enabled=True).first()
        if universal:
            return universal
        # 2. If exactly one enabled domain exists, assume it's the target
        domains = list(Domain.objects.filter(domain_enabled=True))
        if len(domains) == 1:
            return domains[0]

    return None


def _get_default_gateway(domain_name):
    """Find the first enabled gateway for the domain (or global if needed)."""
    from apps.gateways.models import Gateway
    from core.models import Domain
    domain = Domain.objects.filter(domain_name=domain_name).first()
    if domain:
        gw = Gateway.objects.filter(domain=domain, gateway_enabled=True).first()
        if gw:
            return gw.gateway
    # Global fallback if domain-specific not found
    gw = Gateway.objects.filter(domain__isnull=True, gateway_enabled=True).first()
    if gw:
        return gw.gateway
    return None


def generate_directory_xml(domain_name, user=None):
    """Generate directory XML for a domain or specific user."""
    from apps.extensions.models import Extension
    from apps.voicemails.models import Voicemail

    domain = _resolve_domain(domain_name)
    if domain is None:
        return not_found_xml()

    root = etree.Element('document', type='freeswitch/xml')
    section = etree.SubElement(root, 'section', name='directory')
    domain_el = etree.SubElement(section, 'domain', name=domain_name)

    params_el = etree.SubElement(domain_el, 'params')
    etree.SubElement(
        params_el,
        'param',
        name='dial-string',
        value=(
            '{^^:sip_invite_domain=${dialed_domain}'
            ':presence_id=${dialed_user}@${dialed_domain}'
            ':sip_route_uri=${sofia_contact_path(${dialed_user}@${dialed_domain})}}'
            '${sofia_contact(${dialed_user}@${dialed_domain})}'
        ),
    )

    variables_el = etree.SubElement(domain_el, 'variables')
    etree.SubElement(variables_el, 'variable', name='record_stereo', value='true')
    etree.SubElement(variables_el, 'variable', name='default_gateway', value='$${default_provider}')

    groups_el = etree.SubElement(domain_el, 'groups')
    group_el = etree.SubElement(groups_el, 'group', name='default')
    users_el = etree.SubElement(group_el, 'users')

    # Fetch extensions for this domain
    qs = Extension.objects.select_related('tenant').filter(domain=domain, enabled=True)
    if user:
        qs = qs.filter(models.Q(sip_username=user) | models.Q(extension=user))

    # Pre-fetch voicemails for this domain to avoid N+1 queries
    voicemail_map = {
        (vm.tenant_id, vm.voicemail_id): vm
        for vm in Voicemail.objects.filter(domain=domain, voicemail_enabled=True)
    }

    for ext in qs:
        sip_id = ext.sip_username or ext.extension
        user_attrs = {'id': str(sip_id)}
        # number-alias lets FreeSWITCH find the user by plain extension number
        # when dialplan bridges to user/1002@domain instead of user/1002-IHS@domain
        if ext.sip_username and ext.sip_username != ext.extension:
            user_attrs['number-alias'] = ext.extension
        user_el = etree.SubElement(users_el, 'user', **user_attrs)
        params_u = etree.SubElement(user_el, 'params')
        etree.SubElement(params_u, 'param', name='password', value=str(ext.password or ''))

        # Look up the Voicemail box for this extension
        mailbox_id = ext.voicemail_id or ext.extension
        vm = voicemail_map.get((ext.tenant_id, mailbox_id))

        # If a Voicemail box exists, always use its PIN (even if blank = no PIN required).
        # Blank PIN + allow-empty-password-auth=true in voicemail.conf = PIN-less access.
        # Only fall back to extension password when there is no voicemail box at all.
        if vm is not None:
            vm_password = vm.voicemail_password  # explicit blank = PIN-less
        else:
            vm_password = ext.voicemail_password or ext.password or ''
        etree.SubElement(params_u, 'param', name='vm-password', value=str(vm_password))
        if vm and vm.voicemail_mail_to:
            etree.SubElement(params_u, 'param', name='vm-mailto', value=vm.voicemail_mail_to)
        elif ext.voicemail_mail_to:
            etree.SubElement(params_u, 'param', name='vm-mailto', value=ext.voicemail_mail_to)
        if vm:
            etree.SubElement(params_u, 'param', name='vm-min-recording-len', value=str(vm.voicemail_min_len))
            etree.SubElement(params_u, 'param', name='vm-max-recording-len', value=str(vm.voicemail_max_len))
            etree.SubElement(params_u, 'param', name='vm-max-messages', value=str(vm.voicemail_max_messages))

        # Multiline support: set max-calls in params and limit_max in variables.
        # If limit_max is 0, default to 5 to ensure multiple calls are allowed.
        call_limit = str(ext.limit_max if ext.limit_max > 0 else 5)
        etree.SubElement(params_u, 'param', name='max-calls', value=call_limit)

        variables_u = etree.SubElement(user_el, 'variables')
        etree.SubElement(variables_u, 'variable', name='limit_max', value=call_limit)
        etree.SubElement(variables_u, 'variable', name='toll_allow', value=str(ext.toll_allow or ''))
        etree.SubElement(variables_u, 'variable', name='accountcode', value=str(ext.accountcode or ''))
        # Use a per-tenant context so extensions from different tenants
        # cannot call each other (tenant isolation).
        tenant_code = ext.tenant.tenant_code if ext.tenant else None
        user_context = f'default-{tenant_code}' if tenant_code else (ext.user_context or 'default')
        etree.SubElement(variables_u, 'variable', name='user_context', value=user_context)
        etree.SubElement(
            variables_u,
            'variable',
            name='effective_caller_id_name',
            value=str(ext.directory_full_name or ext.effective_caller_id_name or ext.extension),
        )
        etree.SubElement(
            variables_u,
            'variable',
            name='effective_caller_id_number',
            value=str(ext.extension),
        )
        etree.SubElement(
            variables_u,
            'variable',
            name='outbound_caller_id_name',
            value=str(ext.outbound_caller_id_name or ''),
        )
        etree.SubElement(
            variables_u,
            'variable',
            name='outbound_caller_id_number',
            value=str(ext.outbound_caller_id_number or ''),
        )
        etree.SubElement(
            variables_u,
            'variable',
            name='callgroup',
            value=str(ext.call_group or ''),
        )
        if ext.call_timeout:
            etree.SubElement(
                variables_u,
                'variable',
                name='call_timeout',
                value=str(ext.call_timeout),
            )
        if ext.hold_music:
            etree.SubElement(
                variables_u,
                'variable',
                name='hold_music',
                value=str(ext.hold_music),
            )
        etree.SubElement(
            variables_u,
            'variable',
            name='voicemail_enabled',
            value='true' if ext.voicemail_enabled else 'false',
        )
        # voicemail_id: the mailbox this extension deposits into / checks via *98.
        # When a Voicemail box exists we use its UUID so that *98 opens the correct
        # tenant-isolated mailbox — two tenants can have the same extension number (e.g. 901)
        # but each Voicemail row has a unique UUID, preventing cross-tenant mailbox collisions.
        # Falls back to the plain extension number only when no voicemail box is configured.
        mailbox = ext.voicemail_id or ext.extension
        vm_check_id = str(vm.voicemail_uuid) if vm else str(mailbox)
        etree.SubElement(variables_u, 'variable', name='voicemail_id', value=vm_check_id)

        # Codec preference
        codec = ext.absolute_codec_string or ext.codec_preference
        if codec:
            etree.SubElement(variables_u, 'variable', name='absolute_codec_string', value=str(codec))

        # Bypass / proxy media for outbound calls originated by this extension.
        # Directory variables are applied to the A-leg when the user originates a call,
        # so setting bypass_media here covers outbound calls. The dialplan sets it for inbound.
        if ext.sip_bypass_media == 'true':
            etree.SubElement(variables_u, 'variable', name='bypass_media', value='true')
        elif ext.sip_bypass_media == 'proxy':
            etree.SubElement(variables_u, 'variable', name='proxy_media', value='true')

        # Transport restriction
        # 'any' means no restriction — FreeSWITCH defaults to accepting all transports.
        # For wss (WebRTC), also force SRTP and set necessary WebRTC variables.
        transport = getattr(ext, 'transport', 'any') or 'any'
        if transport != 'any':
            etree.SubElement(variables_u, 'variable', name='sip_transport', value=transport)
        webrtc = getattr(ext, 'webrtc_support', False) or transport == 'wss'
        rtp_enc = getattr(ext, 'rtp_encryption', False)
        if webrtc or transport == 'wss':
            # Allow both WebRTC (WSS+SRTP) and plain UDP phones on the same extension.
            # rtp_secure_media=optional means FreeSWITCH uses SRTP if the client offers it,
            # plain RTP otherwise — same behaviour as Asterisk's per-call negotiation.
            etree.SubElement(variables_u, 'variable', name='webrtc', value='true')
            etree.SubElement(variables_u, 'variable', name='rtp_secure_media', value='optional')
        elif rtp_enc:
            # SRTP without full WebRTC mode
            etree.SubElement(variables_u, 'variable', name='rtp_secure_media', value='mandatory')

        # Outbound route — sets default_gateway so the outbound dialplan can use ${default_gateway}
        if ext.outbound_route_id:
            try:
                gateway_name = ext.outbound_route.gateway
                etree.SubElement(variables_u, 'variable', name='default_gateway', value=str(gateway_name))
            except Exception:
                pass

        # Custom outbound SIP X-header — sip_h_X-Name=Value tells FreeSWITCH to inject this header
        if ext.outbound_xheader_name and ext.outbound_xheader_value:
            header_name = ext.outbound_xheader_name.strip()
            if not header_name.startswith('X-'):
                header_name = f'X-{header_name}'
            etree.SubElement(variables_u, 'variable',
                             name=f'sip_h_{header_name}',
                             value=str(ext.outbound_xheader_value))

        # NOTE: Forwarding destinations are intentionally NOT set in the directory.
        # FreeSWITCH would interpret them natively (e.g. forward_user_not_registered_destination
        # causes an automatic transfer loop when set to voicemail:XXX). All forwarding
        # logic is handled exclusively in the dialplan via _extension_to_dialplan_xml.

    # Add parking slots as virtual directory users so FreeSWITCH can respond to
    # BLF SUBSCRIBE requests from phones monitoring park+SLOT@domain.
    if not user:
        from apps.call_parking.models import CallParkingSlot
        slots = CallParkingSlot.objects.select_related('tenant').filter(domain=domain, slot_enabled=True)
        for slot in slots:
            tc = slot.tenant.tenant_code if slot.tenant_id else None
            slot_ext = f'{slot.slot_number}-{tc}' if tc else str(slot.slot_number)
            slot_user = etree.SubElement(users_el, 'user', id=f'park+{slot_ext}')
            slot_vars = etree.SubElement(slot_user, 'variables')
            etree.SubElement(slot_vars, 'variable', name='presence_id', value=f'park+{slot_ext}@{domain_name}')

    return etree.tostring(root, pretty_print=True, xml_declaration=True, encoding='UTF-8').decode()


def _fax_receive_extension_xml(fax, domain_name):
    """Generate a rxfax_<ext> dialplan extension that receives an incoming fax."""
    from django.conf import settings
    webhook_base = getattr(settings, 'FREESWITCH_CALLBACK_URL', 'http://127.0.0.1:8000')

    ext_el = etree.Element('extension', name=f'rxfax_{fax.fax_extension}')
    cond = etree.SubElement(
        ext_el, 'condition',
        field='destination_number',
        expression=f'^rxfax_{re.escape(fax.fax_extension)}$',
    )
    # Stop fax detection first — channel may arrive here via execute_on_fax_detect
    # transfer while spandsp_start_fax_detect is still running on the channel.
    # Both are spandsp apps and conflict if run simultaneously.
    etree.SubElement(cond, 'action', application='spandsp_stop_fax_detect')
    etree.SubElement(cond, 'action', application='answer')
    etree.SubElement(cond, 'action', application='sleep', data='1000')
    etree.SubElement(cond, 'action', application='set', data='fax_enable_t38_request=true')
    etree.SubElement(cond, 'action', application='set', data='fax_enable_t38=true')
    etree.SubElement(cond, 'action', application='set', data='fax_t38_no_ecm=false')
    etree.SubElement(cond, 'action', application='set', data='fax_use_ecm=true')
    
    fax_ident_val = fax.fax_caller_id_name or fax.fax_name or 'IHS PBX'
    etree.SubElement(cond, 'action', application='set', data=f'fax_ident={fax_ident_val}')
    etree.SubElement(cond, 'action', application='set', data=f'fax_header={fax_ident_val}')

    # Store received fax as TIFF.
    # Set the path into a channel variable BEFORE rxfax so that strftime/uuid are
    # expanded at the correct moment and we have a reliable reference for the curl.
    fax_dir = f'/var/lib/freeswitch/fax/received/{domain_name}/{fax.fax_extension}'
    fax_path = f'{fax_dir}/${{strftime(%Y%m%d%H%M%S)}}_${{uuid}}.tif'
    etree.SubElement(cond, 'action', application='system', data=f'mkdir -p {fax_dir}')
    # Capture the expanded path (strftime + uuid evaluated now) into a channel var
    etree.SubElement(cond, 'action', application='set', data=f'fax_storage_path={fax_path}')
    etree.SubElement(cond, 'action', application='rxfax', data='${fax_storage_path}')

    # Notify Django webhook after receive; use ${fax_storage_path} — reliable vs
    # ${fax_local_filename} which is not set by all spandsp/FreeSWITCH versions.
    # fax_document_transferred_pages = pages actually received (correct spandsp var).
    # fax_did_number = original DID dialled (${sip_to_user} survives the transfer).
    # fax_mailbox   = the fax box extension (logical mailbox identifier).
    # Use single quotes for FS variables to mitigate shell injection
    curl_cmd = (
        f'curl -s -X POST {webhook_base}/api/v1/fax/received/'
        f' -F "fax_uuid={fax.fax_uuid}"'
        f' -F "fax_file=${{fax_storage_path}}"'
        f' -F "fax_success=${{fax_success}}"'
        f' -F "fax_pages=${{fax_document_transferred_pages}}"'
        f' -F "fax_result_text=${{fax_result_text}}"'
        f' -F "fax_remote_station_id=\'${{fax_remote_station_id}}\'"'
        f' -F "caller_id_number=\'${{caller_id_number}}\'"'
        f' -F "caller_id_name=\'${{caller_id_name}}\'"'
        f' -F "fax_did_number=\'${{fax_did_number}}\'"'
        f' -F "fax_mailbox={fax.fax_extension}"'
        f' -F "domain_name={domain_name}"'
    )
    etree.SubElement(cond, 'action', application='system', data=curl_cmd)
    return ext_el


def _get_default_gateway(domain_name):
    """Return the gateway name to use for external bridging.

    Looks up the first enabled outbound route for the domain and returns its
    gateway name.  Falls back to the FreeSWITCH global variable
    ${default_provider} if no outbound route is found.
    """
    try:
        from core.models import Domain
        from apps.outbound_routes.models import OutboundRoute
        base_qs = OutboundRoute.objects.filter(
            outbound_route_enabled=True, gateway__isnull=False
        ).select_related('gateway').order_by('outbound_route_order', 'outbound_route_name')

        # Try domain-specific route first
        domain_obj = Domain.objects.filter(domain_name=domain_name).first()
        if domain_obj:
            route = base_qs.filter(domain=domain_obj).first()
            if route and route.gateway:
                return route.gateway.gateway

        # Fall back to any enabled route (domain-less or cross-domain)
        route = base_qs.first()
        if route and route.gateway:
            return route.gateway.gateway
    except Exception:
        pass
    return '${default_provider}'


def _resolve_dest_action(dest, domain_name, preload=None):
    """
    Resolve dest_type + dest_target_uuid to a list of (application, data) tuples.
    Returns the FreeSWITCH actions needed to route the call.
    """
    dtype = dest.dest_type
    target = dest.dest_target_uuid

    def _tenant_ctx(obj):
        """Return 'default-{tenant_code}' or 'default' for the given model instance."""
        code = obj.tenant.tenant_code if obj.tenant else None
        return f'default-{code}' if code else 'default'

    def _pl_get(key, uuid):
        if preload is not None:
            return preload[key].get(str(uuid))
        return None  # caller must fall back to DB query (no preload path for this key)

    try:
        if dtype == 'extension':
            from apps.extensions.models import Extension
            ext = _pl_get('extensions', target) or Extension.objects.get(extension_uuid=target)
            return [('transfer', f'{ext.extension} XML {_tenant_ctx(ext)}')]

        elif dtype == 'ivr_menu':
            from apps.ivr_menus.models import IvrMenu
            ivr = _pl_get('ivr_menus', target) or IvrMenu.objects.get(ivr_menu_uuid=target)
            return [('transfer', f'{ivr.ivr_menu_extension} XML {_tenant_ctx(ivr)}')]

        elif dtype == 'ring_group':
            from apps.ring_groups.models import RingGroup
            rg = _pl_get('ring_groups', target) or RingGroup.objects.get(ring_group_uuid=target)
            return [('transfer', f'{rg.ring_group_extension} XML {_tenant_ctx(rg)}')]

        elif dtype == 'voicemail':
            from apps.extensions.models import Extension
            ext = _pl_get('extensions', target) or Extension.objects.get(extension_uuid=target)
            return [
                ('answer', ''),
                ('sleep', '1000'),
                ('voicemail', f'default {domain_name} {ext.extension}'),
            ]

        elif dtype == 'time_condition':
            from apps.time_conditions.models import TimeCondition
            tc = _pl_get('time_conditions', target) or TimeCondition.objects.get(dialplan_uuid=target)
            return [('transfer', f'{tc.dialplan_extension} XML {_tenant_ctx(tc)}')]

        elif dtype == 'working_hours':
            from apps.working_hours.models import WorkingHours
            wh = _pl_get('working_hours', target) or WorkingHours.objects.get(working_hours_uuid=target)
            return [('transfer', f'{wh.dialplan_extension} XML {_tenant_ctx(wh)}')]

        elif dtype == 'call_flow':
            from apps.call_flows.models import CallFlow
            cf = _pl_get('call_flows', target) or CallFlow.objects.get(call_flow_uuid=target)
            return [('transfer', f'{cf.call_flow_extension} XML {_tenant_ctx(cf)}')]

        elif dtype == 'conference':
            from apps.conferences.models import ConferenceProfile
            conf = _pl_get('conferences', target) or ConferenceProfile.objects.get(conference_profile_uuid=target)
            return [('answer', ''), ('conference', conf.conference_profile_name)]

        elif dtype == 'external':
            number = dest.dest_external_number or ''
            if number:
                gw = _get_default_gateway(domain_name)
                return [('bridge', f'sofia/gateway/{gw}/{number}')]

        elif dtype == 'call_forward':
            number = dest.dest_external_number or ''
            if number:
                gw = _get_default_gateway(domain_name)
                return [
                    ('set', 'effective_caller_id_number=${caller_id_number}'),
                    ('set', 'effective_caller_id_name=${caller_id_name}'),
                    ('set', 'ignore_early_media=true'),
                    ('bridge', f'sofia/gateway/{gw}/{number}'),
                ]

        elif dtype == 'fax':
            fax_box = dest.fax
            if fax_box:
                tenant_code = fax_box.tenant.tenant_code if fax_box.tenant else None
                fax_ctx = f'default-{tenant_code}' if tenant_code else 'public'
                return [('transfer', f'rxfax_{fax_box.fax_extension} XML {fax_ctx}')]
            return [('hangup', 'NORMAL_CLEARING')]

        elif dtype == 'hangup':
            return [('hangup', 'NORMAL_CLEARING')]

        elif dtype == 'custom_destination':
            from apps.custom_destinations.models import CustomDestination
            cd = _pl_get('custom_dests', target) or CustomDestination.objects.get(custom_destination_uuid=target)
            # Proxy: resolve the underlying destination type
            return _resolve_dest_action(cd, domain_name, preload=preload)

        elif dtype == 'call_park':
            from apps.call_parking.models import CallParkingSlot
            slot_obj = _pl_get('parking_slots', target) or CallParkingSlot.objects.select_related('domain', 'tenant').get(call_parking_slot_uuid=target)
            slot_domain = slot_obj.domain.domain_name
            tc = slot_obj.tenant.tenant_code if slot_obj.tenant_id else None
            slot_ext = f'{slot_obj.slot_number}-{tc}' if tc else str(slot_obj.slot_number)
            moh = slot_obj.music_on_hold or '$${hold_music}'
            timeout = slot_obj.parking_timeout or 60
            actions = [
                ('export', f'presence_id=park+{slot_ext}@{slot_domain}'),
                ('set', f'valet_hold_music={moh}'),
                ('set', f'valet_park_timeout={timeout}'),
            ]
            if slot_obj.timeout_action == 'return_to_parker':
                actions.append(('set', 'valet_park_return_to_parker=true'))
            elif slot_obj.timeout_action == 'voicemail' and slot_obj.timeout_voicemail_extension:
                actions.append(('set', 'valet_park_timeout_app=voicemail'))
                actions.append(('set', f'valet_park_timeout_data=default {slot_domain} {slot_obj.timeout_voicemail_extension}'))
            actions.append(('valet_park', f'valet_parking_lot@{slot_domain} {slot_ext}'))
            return actions

    except Exception as e:
        logger.error('DID %s: exception resolving dest_type=%s target=%s: %s',
                     dest.destination_number, dtype, target, e)

    logger.warning('DID %s: could not resolve dest_type=%s target=%s',
                   dest.destination_number, dtype, target)
    return [('hangup', 'NORMAL_CLEARING')]


def _destination_to_extension_xml(dest, domain_name, caller_id_number='', preload=None):
    """Convert a Destination (DID) record into a FreeSWITCH <extension> element (public context)."""
    safe_name = re.sub(r'[^a-zA-Z0-9_]', '_', dest.destination_number)
    ext_el = etree.Element('extension', name=f'did_{safe_name}')

    # Use stored regex or match the literal DID number exactly.
    # Normalize E.164 (+1XXXXXXXXXX) to match both +1XXXXXXXXXX and XXXXXXXXXX
    # since carriers (e.g. Bandwidth) often send 10-digit without +1.
    if dest.destination_number_regex:
        regex = dest.destination_number_regex
    else:
        num = dest.destination_number
        m = re.match(r'^\+1(\d{10})$', num)
        if m:
            # Improved regex to handle international and raw digits
            regex = rf'^(\+)?(\d+)?{m.group(1)}$'
        else:
            regex = re.escape(num)
    if not regex.startswith('^'):
        regex = f'^{regex}$'
    cond = etree.SubElement(ext_el, 'condition', field='destination_number', expression=regex)

    # Always set domain so transfer to default context works
    etree.SubElement(cond, 'action', application='set', data=f'domain_name={domain_name}')
    # Capture the original DID for the fax webhook
    etree.SubElement(cond, 'action', application='set', data='fax_did_number=${destination_number}')

    # Fax detection on a shared voice+fax DID.
    #
    # The inbound (DID) leg is only "answered" when a human picks up the
    # bridged extension, and a calling fax machine sends little/no CNG before
    # the line is answered — so neither an execute_on_answer trigger nor
    # early-media (pre_answer) detection reliably catches a fax-only sender;
    # the call just rings until the carrier CANCELs.
    #
    # Instead we ANSWER the inbound leg up front and listen for fax tone for a
    # short detection window BEFORE ringing the extension. This way a fax call
    # never rings the phone:
    #   - If fax tone is heard during the window, execute_on_fax_detect fires
    #     immediately (even mid-sleep) and transfers to rxfax — the extension
    #     is never bridged, so it never rings.
    #   - If no fax tone by the end of the window, we stop detection and fall
    #     through to the normal routing actions below, which ring the extension
    #     as a regular voice call.
    # The tradeoff is that voice callers wait FAX_DETECT_WINDOW_MS after answer
    # before the phone starts ringing.
    if dest.fax_id and dest.fax_receive and dest.dest_type != 'fax':
        fax_box = dest.fax
        tenant_code = fax_box.tenant.tenant_code if fax_box.tenant else None
        fax_ctx = f'default-{tenant_code}' if tenant_code else 'public'
        # Shared voice+fax detection:
        # 1. Answer the inbound leg immediately so the fax machine gets live
        #    media and starts T.30 negotiation (produces detectable tone).
        # 2. Start spandsp fax detection.
        # 3. Sleep for a detection window — execute_on_fax_detect fires
        #    asynchronously mid-sleep if fax tone is heard, transferring to
        #    rxfax BEFORE the sleep completes (extension never rings).
        # 4. After the window, stop detection and let the call fall through
        #    to the routing actions below, which ring the extension normally.
        # Voice callers wait FAX_DETECT_WINDOW_MS before the phone rings.
        # Do NOT call spandsp_stop_fax_detect before the routing actions —
        # that races against a late-firing execute_on_fax_detect and can
        # cancel detection just as the tone is being confirmed.
        FAX_DETECT_WINDOW_MS = 4000
        etree.SubElement(
            cond, 'action', application='set',
            data=f'execute_on_fax_detect=transfer rxfax_{fax_box.fax_extension} XML {fax_ctx}',
        )
        etree.SubElement(cond, 'action', application='answer')
        etree.SubElement(cond, 'action', application='spandsp_start_fax_detect')
        etree.SubElement(cond, 'action', application='sleep', data=str(FAX_DETECT_WINDOW_MS))

    # Optional call enhancements
    if dest.destination_cid_name_prefix:
        etree.SubElement(cond, 'action', application='set',
                         data=f'effective_caller_id_name={dest.destination_cid_name_prefix}${{caller_id_name}}')
    if dest.destination_ringback:
        etree.SubElement(cond, 'action', application='set',
                         data=f'ringback={dest.destination_ringback}')
    if dest.destination_hold_music:
        etree.SubElement(cond, 'action', application='set',
                         data=f'hold_music={dest.destination_hold_music}')
    if dest.destination_accountcode:
        etree.SubElement(cond, 'action', application='set',
                         data=f'accountcode={dest.destination_accountcode}')
    if dest.destination_record:
        _add_recording_actions(cond, domain_name)
    # Callback-to-last-caller: if enabled on the DID or on the resolved custom destination,
    # look up the most recent answered outbound call to that number and route there.
    routed_to_last = False
    effective_callback = dest.callback_to_last_caller
    if not effective_callback and dest.dest_type == 'custom_destination' and dest.dest_target_uuid:
        try:
            from apps.custom_destinations.models import CustomDestination
            cd = CustomDestination.objects.get(custom_destination_uuid=dest.dest_target_uuid)
            effective_callback = cd.callback_to_last_caller
        except Exception:
            pass
    if effective_callback and dest.tenant_id:
        # Sticky last-agent routing.
        #
        # Emit a Lua action that runs at call-execute time, NOT a static transfer
        # baked into the cached XML. Reason: mod_xml_curl caches dialplan responses
        # by destination_number alone; if we baked the sticky extension into the
        # XML it would only be correct for the first caller, then every subsequent
        # caller to this DID would get bridged to the same wrong extension. The
        # Lua reads caller_id_number live from the session and queries
        # v_caller_extension_affinity at execute time.
        #
        # The fallback is what the CustomDestination wrapping this DID configured
        # (its dest_type / dest_target_uuid) — used when no affinity match exists.
        tenant_code = dest.tenant.tenant_code if dest.tenant else None
        ctx = f'default-{tenant_code}' if tenant_code else 'default'

        fb_type = 'hangup'
        fb_data = ''
        if dest.dest_type == 'custom_destination' and dest.dest_target_uuid:
            try:
                from apps.custom_destinations.models import CustomDestination
                cd = CustomDestination.objects.get(custom_destination_uuid=dest.dest_target_uuid)
                if cd.dest_type == 'extension' and cd.dest_target_uuid:
                    # Look up the extension number for the fallback
                    from apps.extensions.models import Extension
                    fb_ext = Extension.objects.filter(extension_uuid=cd.dest_target_uuid).only('extension').first()
                    if fb_ext:
                        fb_type = 'extension'
                        fb_data = str(fb_ext.extension)
                elif cd.dest_type == 'external' and cd.dest_external_number:
                    fb_type = 'transfer'
                    fb_data = f'{cd.dest_external_number} XML public'
            except Exception:
                pass

        etree.SubElement(
            cond, 'action', application='lua',
            data=f'affinity_route.lua {dest.tenant_id} {fb_type} {fb_data} {ctx}',
        )
        routed_to_last = True

    if not routed_to_last:
        # Resolve destination type → FreeSWITCH routing actions
        for app, data in _resolve_dest_action(dest, domain_name, preload=preload):
            etree.SubElement(cond, 'action', application=app, data=data)

    return ext_el


def _outbound_route_to_xml(route):
    """Generate a FreeSWITCH <extension> element for one outbound route.

    The pattern should capture the digits-to-dial in group 1 (e.g. ^9(\\d{10})$).
    The bridge string is built as: sofia/gateway/<gw>/<prepend>$1
    Multiple gateways are joined with '|' for sequential failover.
    """
    safe_name = route.outbound_route_name.replace(' ', '_').replace('.', '_')
    ext_el = etree.Element('extension', name=f'outbound.{safe_name}')
    cond = etree.SubElement(ext_el, 'condition',
                            field='destination_number',
                            expression=route.dialplan_pattern)

    # Save captured digits ($1) into a channel var so it survives across conditions.
    etree.SubElement(cond, 'action', application='set', data='outbound_digits=$1')
    etree.SubElement(cond, 'action', application='set', data='hangup_after_bridge=true')
    # Set caller ID: route config takes priority, then directory value (already set).
    cid_number = route.caller_id_number or '${outbound_caller_id_number}'
    cid_name = route.caller_id_name or route.caller_id_number or '${outbound_caller_id_name}'
    etree.SubElement(cond, 'action', application='set', data=f'effective_caller_id_number={cid_number}')
    etree.SubElement(cond, 'action', application='set', data=f'effective_caller_id_name={cid_name}')
    # Force PCMU on leg B (toward the gateway) — Bandwidth only accepts PCMU.
    etree.SubElement(cond, 'action', application='set', data='bridge_codec_string=PCMU')
    etree.SubElement(cond, 'action', application='export', data='nolocal:absolute_codec_string=PCMU')
    # Skip entire extension if destination doesn't match; continue to CID/bridge conditions if it does.
    cond.set('break', 'on-false')

    # Override CID with X-OverrideCID header when present — must run before the bridge fires.
    override_cond = etree.SubElement(ext_el, 'condition',
                                     field='${sip_h_X-OverrideCID}',
                                     expression=r'^(.+)$')
    override_cond.set('break', 'never')
    etree.SubElement(override_cond, 'action', application='set',
                     data='effective_caller_id_number=${sip_h_X-OverrideCID}')
    etree.SubElement(override_cond, 'action', application='set',
                     data='effective_caller_id_name=${sip_h_X-OverrideCID}')

    # Final condition always matches — bridge using saved digits var, not $1.
    bridge_cond = etree.SubElement(ext_el, 'condition')
    gateways = [g for g in [route.gateway, route.gateway_2, route.gateway_3] if g]
    if gateways:
        prepend = route.prepend or ''
        parts = [f'sofia/gateway/{gw.gateway}/{prepend}${{outbound_digits}}' for gw in gateways]
        _add_recording_actions(bridge_cond, '${domain_name}')
        etree.SubElement(bridge_cond, 'action', application='bridge', data='|'.join(parts))
    else:
        # No gateway configured — log and drop
        logger.warning('OutboundRoute "%s" has no gateway assigned; calls will be rejected',
                       route.outbound_route_name)
        etree.SubElement(bridge_cond, 'action', application='hangup', data='NORMAL_CLEARING')

    return ext_el


def _add_voicemail_actions(cond_el, domain_name, mailbox, vm):
    """Append answer + voicemail actions to a condition element.

    mailbox is kept for storage path / greeting lookup but the voicemail UUID
    is used as the username stored in voicemail_msgs so it is globally unique
    and tenant-bound by definition.
    """
    etree.SubElement(cond_el, 'action', application='answer')
    etree.SubElement(cond_el, 'action', application='sleep', data='1000')
    greeting = getattr(vm, 'voicemail_greeting', None) if vm else None
    # Use voicemail UUID as the mailbox identifier — globally unique, tenant-bound.
    vm_uuid_str = str(vm.voicemail_uuid) if vm else mailbox
    storage_dir = f'/var/lib/freeswitch/storage/voicemail/default/{domain_name}/{vm_uuid_str}'
    ingest_url = 'http://127.0.0.1:8000/api/v1/voicemail-messages/ingest/'

    # Max recording length: per-mailbox setting, then tenant setting, then default 120s
    max_len = 120
    if vm and getattr(vm, 'voicemail_max_len', None):
        max_len = vm.voicemail_max_len
    elif vm and getattr(vm, 'domain', None) and getattr(vm.domain, 'tenant', None):
        t = vm.domain.tenant
        if getattr(t, 'voicemail_timeout', 0):
            max_len = t.voicemail_timeout

    def _add_record_and_ingest():
        """Add set+record actions. Uses execute_on_record_stop to run ingest
        curl when recording ends, whether caller hangs up or max time is reached."""
        etree.SubElement(cond_el, 'action', application='system',
                         data=f'mkdir -p {storage_dir}')
        etree.SubElement(cond_el, 'action', application='set',
                         data='vm_uuid=${create_uuid()}')
        curl_cmd = (
            f'curl -s -X POST {ingest_url}'
            f' -F uuid=${{vm_uuid}}'
            f' -F username={vm_uuid_str}'
            f' -F domain={domain_name}'
            f' -F "file_path={storage_dir}/msg_${{vm_uuid}}.wav"'
            f' -F "cid_name=\'${{caller_id_name}}\'"'
            f' -F "cid_number=\'${{caller_id_number}}\'"'
            f' -F created_epoch=${{epoch}}'
        )
        etree.SubElement(cond_el, 'action', application='set',
                         data=f'execute_on_record_stop=system:{curl_cmd}')
        etree.SubElement(cond_el, 'action', application='record',
                         data=f'{storage_dir}/msg_${{vm_uuid}}.wav {max_len} 0 0')
        etree.SubElement(cond_el, 'action', application='hangup')

    if greeting == 'tts_name':
        tts_text = (
            (vm.tts_greeting_text.strip() if vm and vm.tts_greeting_text else '')
            or f'You have reached extension {mailbox}. Please leave a message after the beep.'
        )
        # Sanitize: remove pipe chars used as flite separator
        tts_text = tts_text.replace('|', ' ')[:400]
        etree.SubElement(cond_el, 'action', application='speak',
                         data=f'flite|kal|{tts_text}')
        etree.SubElement(cond_el, 'action', application='playback',
                         data='tone_stream://%(500,0,640)')
        _add_record_and_ingest()

    elif greeting == 'recorded_name':
        name_wav = f'{storage_dir}/recorded_name.wav'
        etree.SubElement(cond_el, 'action', application='playback', data=name_wav)
        etree.SubElement(cond_el, 'action', application='playback',
                         data='tone_stream://%(500,0,640)')
        _add_record_and_ingest()

    else:
        # auto_with_instructions (default) — use FreeSWITCH built-in voicemail prompt phrase
        etree.SubElement(cond_el, 'action', application='phrase',
                         data='voicemail_record_message')
        _add_record_and_ingest()


def _extension_to_dialplan_xml(ext, domain_name, vm=None):
    """Auto-generate FreeSWITCH <extension> elements for a local extension (default context).

    Returns a list of <extension> elements to append to the context in order.

    Call routing priority:
      1. Unconditional forward (forward_all) — bypasses everything else
      2. Offline detection — if extension not registered:
           a. forward_user_not_registered (if set)
           b. hangup immediately (no silent ring, no voicemail)
      3. Bridge to registered extension
      4. On busy → forward_busy → voicemail → hangup (first match)
      5. On no answer → forward_no_answer → voicemail → hangup (first match)

    Voicemail is only a fallback when voicemail_enabled=True AND no forwarding rule applies.
    """
    cf_active = ext.call_forward_active
    sip_id = ext.sip_username or ext.extension
    mailbox = ext.voicemail_id or ext.extension
    # Match both the plain extension (902) and the SIP username (902-IHS) so that
    # BLF keys dialing the full SIP username are routed correctly.
    if ext.sip_username and ext.sip_username != ext.extension:
        dest_expr = f'^({re.escape(ext.extension)}|{re.escape(ext.sip_username)})$'
    else:
        dest_expr = f'^{re.escape(ext.extension)}$'

    def _fwd_dest(destination):
        """Return list of (app, data) tuples for a forwarding destination."""
        tenant_code = ext.tenant.tenant_code if ext.tenant else None
        ctx = f'default-{tenant_code}' if tenant_code else 'default'
        if destination.startswith('voicemail:'):
            vm_id = destination[len('voicemail:'):]
            return [('answer', None), ('sleep', '1000'), ('voicemail', f'default {domain_name} {vm_id}')]
        if re.match(r'^\d{1,10}$', destination) or re.match(r'^(wh|tc|ivr|rg|cf|park|conf)_', destination):
            return [
                ('log', f'INFO Extension Forwarding: {ext.extension} to {destination} (transfer)'),
                ('transfer', f'{destination} XML {ctx}')
            ]
        return [
            ('log', f'INFO Extension Forwarding: {ext.extension} to {destination} (bridge)'),
            ('bridge', f'sofia/gateway/{destination}')
        ]

    def _apply_fwd_dest(cond_el, destination):
        """Append forwarding actions to cond_el, respecting voicemail greeting style."""
        if destination.startswith('voicemail:'):
            vm_id = destination[len('voicemail:'):]
            # Use vm passed into _extension_to_dialplan_xml if it matches, else look up
            target_vm = vm if (vm and (vm.voicemail_id or ext.extension) == vm_id) else None
            if target_vm is None:
                from apps.voicemails.models import Voicemail as _VM
                target_vm = _VM.objects.filter(
                    voicemail_id=vm_id, voicemail_enabled=True, tenant=ext.tenant
                ).first()
            _add_voicemail_actions(cond_el, domain_name, vm_id, target_vm)
        else:
            for app, data in _fwd_dest(destination):
                el = etree.SubElement(cond_el, 'action', application=app)
                if data is not None:
                    el.set('data', data)

    # ── 1. Unconditional forward ──────────────────────────────────────────
    if cf_active and ext.forward_all_enabled and ext.forward_all_destination:
        fwd_el = etree.Element('extension', name=f'ext_{ext.extension}')
        cond = etree.SubElement(fwd_el, 'condition', field='destination_number', expression=dest_expr)
        etree.SubElement(cond, 'action', application='set', data='hangup_after_bridge=true')
        _apply_fwd_dest(cond, ext.forward_all_destination)
        return [fwd_el]

    elements = []

    # ── 1b. Condition-based forward ──────────────────────────────────────────
    if cf_active and ext.forward_on_condition_enabled and ext.forward_on_condition and ext.forward_on_condition_destination:
        cond_el = etree.Element('extension', name=f'ext_{ext.extension}_cond')
        num_cond = etree.SubElement(cond_el, 'condition', field='destination_number', expression=dest_expr)
        num_cond.set('break', 'on-false')
        # Evaluate the user's condition string using FreeSWITCH cond function
        eval_expr = f'${{cond({ext.forward_on_condition} ? true : false)}}'
        eval_cond = etree.SubElement(cond_el, 'condition', field=eval_expr, expression='^true$')
        eval_cond.set('break', 'on-true')
        etree.SubElement(eval_cond, 'action', application='set', data='hangup_after_bridge=true')
        _apply_fwd_dest(eval_cond, ext.forward_on_condition_destination)
        elements.append(cond_el)

    # ── 2. Offline detection ──────────────────────────────────────────────
    # sofia_contact returns 'error/no-such-user' when extension is not registered.
    # Check BEFORE attempting bridge so offline calls never ring into silence.
    offline_el = etree.Element('extension', name=f'ext_{ext.extension}_offline')
    offline_dest_cond = etree.SubElement(offline_el, 'condition',
                                         field='destination_number', expression=dest_expr)
    offline_reg_cond = etree.SubElement(offline_el, 'condition',
                                        field=f'${{sofia_contact({sip_id}@{domain_name})}}',
                                        expression=r'^(error|$)')
    # Always tag the target extension so CDR ingest can record it
    etree.SubElement(offline_reg_cond, 'action', application='set',
                     data=f'dialed_extension={ext.extension}')
    # If tenant has push notifications enabled or extension has mobile push enabled,
    # park the call so the ESL listener can send a push webhook and poll for the extension to register.
    # The ESL listener will handle forwarding/hangup after the poll timeout.
    is_push_enabled = False
    if ext.tenant and getattr(ext.tenant, 'push_notifications_enabled', False):
        is_push_enabled = True
    elif getattr(ext, 'mobile_push_enabled', False):
        is_push_enabled = True

    if is_push_enabled:
        etree.SubElement(offline_reg_cond, 'action', application='set', data='ringback=${us-ring}')
        etree.SubElement(offline_reg_cond, 'action', application='ring_ready')
        etree.SubElement(offline_reg_cond, 'action', application='park')
    elif cf_active and ext.forward_user_not_registered_enabled and ext.forward_user_not_registered_destination:
        _apply_fwd_dest(offline_reg_cond, ext.forward_user_not_registered_destination)
    elif ext.voicemail_enabled:
        _add_voicemail_actions(offline_reg_cond, domain_name, mailbox, vm)
    else:
        etree.SubElement(offline_reg_cond, 'action', application='hangup',
                         data='USER_NOT_REGISTERED')
    elements.append(offline_el)

    # ── 3. Bridge with inline post-bridge fallback ───────────────────────
    # FusionPBX pattern: single condition, actions after bridge only execute
    # when bridge FAILS (continue_on_fail=true). When bridge succeeds,
    # hangup_after_bridge=true terminates the call — nothing after bridge runs.
    bridge_el = etree.Element('extension', name=f'ext_{ext.extension}_bridge')

    # Bridge condition — destination match + pre-bridge channel var setup
    bridge_cond = etree.SubElement(bridge_el, 'condition',
                                   field='destination_number', expression=dest_expr)
    etree.SubElement(bridge_cond, 'action', application='set',
                     data=f'dialed_extension={ext.extension}')
    if ext.call_timeout:
        etree.SubElement(bridge_cond, 'action', application='set',
                         data=f'call_timeout={ext.call_timeout}')
    etree.SubElement(bridge_cond, 'action', application='set', data='ringback=${us-ring}')
    etree.SubElement(bridge_cond, 'action', application='set', data='transfer_ringback=${us-ring}')
    etree.SubElement(bridge_cond, 'action', application='set', data='hangup_after_bridge=true')
    # Only continue on actual failure causes — NOT on NORMAL_CLEARING (remote hangup).
    # Without this restriction, a normal remote hangup falls through to fallback actions
    # which can re-originate or transfer the call, causing an infinite redial loop.
    etree.SubElement(bridge_cond, 'action', application='set',
                     data='continue_on_fail=USER_BUSY,NO_ANSWER,NO_ROUTE_DESTINATION,'
                          'ALLOTTED_TIMEOUT,CALL_REJECTED,USER_NOT_REGISTERED,'
                          'NO_USER_RESPONSE,SUBSCRIBER_ABSENT')

    # Bypass / proxy media — set before bridge so it applies to the inbound leg
    if ext.sip_bypass_media == 'true':
        etree.SubElement(bridge_cond, 'action', application='set', data='bypass_media=true')
        etree.SubElement(bridge_cond, 'action', application='export',
                         data='nolocal:absolute_codec_string=PCMU')
    elif ext.sip_bypass_media == 'proxy':
        etree.SubElement(bridge_cond, 'action', application='set', data='proxy_media=true')
        etree.SubElement(bridge_cond, 'action', application='export',
                         data='nolocal:absolute_codec_string=PCMU')

    if ext.reject_to_voicemail:
        etree.SubElement(bridge_cond, 'action', application='set',
                         data='fail_on_single_reject=USER_BUSY,CALL_REJECTED,603')
    _add_recording_actions(bridge_cond, domain_name)
    # Ring ALL registered contacts simultaneously (desk phone + softphone, etc.).
    # sofia_contact(*/user@domain) expands to a comma-joined dial string of every
    # active registration; user/user@domain would only ring the most recent one.
    etree.SubElement(bridge_cond, 'action', application='bridge',
                     data=f'${{sofia_contact(*/{sip_id}@{domain_name})}}')

    # ── 4. Post-bridge fallback ───────────────────────────────────────────
    # Actions below this line only execute when bridge FAILS (continue_on_fail=true).
    # When bridge succeeds, hangup_after_bridge=true terminates the call before
    # reaching these actions.
    #
    # Strategy: save BRIDGE_HANGUP_CAUSE to a channel var, then transfer to
    # dedicated fallback extensions that can inspect it and branch.
    has_busy_fwd = cf_active and ext.forward_busy_enabled and ext.forward_busy_destination
    has_noanswer_fwd = cf_active and ext.forward_no_answer_enabled and ext.forward_no_answer_destination
    ctx_name = f'default-{ext.tenant.tenant_code}' if ext.tenant else 'default'

    if has_busy_fwd or has_noanswer_fwd:
        etree.SubElement(bridge_cond, 'action', application='transfer',
                         data=f'ext_{ext.extension}_fallback XML {ctx_name}')

        # Fallback extension: matched by destination_number via transfer above.
        # Uses last_bridge_hangup_cause which FreeSWITCH sets automatically and
        # preserves across transfers (unlike BRIDGE_HANGUP_CAUSE which is cleared).
        fallback_name = f'ext_{ext.extension}_fallback'
        busy_el = etree.Element('extension', name=fallback_name)
        # Entry condition: match the transferred-to destination name (always true).
        entry_cond = etree.SubElement(busy_el, 'condition',
                                      field='destination_number',
                                      expression=f'^{fallback_name}$')
        entry_cond.set('break', 'on-false')

        # Busy branch
        busy_cond = etree.SubElement(busy_el, 'condition',
                                     field='${last_bridge_hangup_cause}', expression='^USER_BUSY$')
        busy_cond.set('break', 'on-true')
        if has_busy_fwd:
            _apply_fwd_dest(busy_cond, ext.forward_busy_destination)
        elif ext.voicemail_enabled:
            _add_voicemail_actions(busy_cond, domain_name, mailbox, vm)
        else:
            etree.SubElement(busy_cond, 'action', application='hangup', data='USER_BUSY')

        # No-answer catch-all branch
        noanswer_cond = etree.SubElement(busy_el, 'condition',
                                         field='${last_bridge_hangup_cause}',
                                         expression=r'^\S+')
        noanswer_cond.set('break', 'on-true')
        if has_noanswer_fwd:
            _apply_fwd_dest(noanswer_cond, ext.forward_no_answer_destination)
        elif ext.voicemail_enabled:
            _add_voicemail_actions(noanswer_cond, domain_name, mailbox, vm)
        else:
            etree.SubElement(noanswer_cond, 'action', application='hangup', data='NO_ANSWER')

    elif ext.voicemail_enabled:
        # No forwarding — go straight to voicemail on any failure
        _add_voicemail_actions(bridge_cond, domain_name, mailbox, vm)
    else:
        etree.SubElement(bridge_cond, 'action', application='hangup', data='NO_ANSWER')

    elements.append(bridge_el)
    if has_busy_fwd or has_noanswer_fwd:
        elements.append(busy_el)

    return elements


def _convert_time_to_server_tz(t, wh_tz_str):
    """Convert a time from the working hours timezone to UTC (the FreeSWITCH server clock).

    FreeSWITCH time-of-day conditions are matched against the server's clock.
    The server runs in UTC, so we always convert to UTC regardless of Django's TIME_ZONE.
    Returns (utc_time, day_offset) where day_offset is -1, 0, or +1.
    """
    try:
        wh_tz = ZoneInfo(wh_tz_str or 'UTC')
        utc_tz = ZoneInfo('UTC')
        ref_date = datetime(2024, 1, 1, t.hour, t.minute, t.second, tzinfo=wh_tz)
        converted = ref_date.astimezone(utc_tz)
        day_offset = converted.date().day - ref_date.date().day
        
        # console log for debugging generation
        print(f"DEBUG: {t} ({wh_tz_str}) -> {converted.time()} (UTC) offset={day_offset}")
        
        if day_offset > 1: day_offset = 1
        elif day_offset < -1: day_offset = -1
        return converted.time(), day_offset
    except Exception as e:
        print(f"WARNING: Timezone conversion failed for {wh_tz_str}: {e}")
        return t, 0



def _iso_to_fs_wday(iso_day):
    """Convert ISO weekday (1=Mon…7=Sun) to FreeSWITCH wday (1=Sun…7=Sat).

    Formula: fs_wday = (iso_day % 7) + 1
      Mon(1)→2, Tue(2)→3, Wed(3)→4, Thu(4)→5, Fri(5)→6, Sat(6)→7, Sun(7)→1
    """
    return (iso_day % 7) + 1


def _resolve_wh_dest(wh, when, domain_name, ctx, preload=None):
    """Resolve a WorkingHours open/closed destination to a list of (app, data) tuples."""
    if when == 'open':
        dest_type = wh.open_dest_type
        target = wh.open_dest_target_uuid
        external = wh.open_dest_external_number
    else:
        dest_type = wh.closed_dest_type
        target = wh.closed_dest_target_uuid
        external = wh.closed_dest_external_number

    return _resolve_wh_dest_from_type(dest_type, target, external, domain_name, ctx, preload=preload)


def _resolve_wh_dest_from_type(dest_type, target, external, domain_name, ctx, preload=None):
    """Inner resolver used by _resolve_wh_dest to avoid repeating logic."""

    def _pl_get(key, uuid):
        if preload is not None:
            return preload[key].get(str(uuid))
        return None

    try:
        if dest_type == 'extension':
            from apps.extensions.models import Extension
            ext = _pl_get('extensions', target) or Extension.objects.get(extension_uuid=target)
            return [('transfer', f'{ext.extension} XML {ctx}')]
        elif dest_type == 'ring_group':
            from apps.ring_groups.models import RingGroup
            rg = _pl_get('ring_groups', target) or RingGroup.objects.get(ring_group_uuid=target)
            return [('transfer', f'{rg.ring_group_extension} XML {ctx}')]
        elif dest_type == 'voicemail':
            from apps.extensions.models import Extension
            ext = _pl_get('extensions', target) or Extension.objects.get(extension_uuid=target)
            return [('answer', ''), ('sleep', '1000'), ('voicemail', f'default {domain_name} {ext.extension}')]
        elif dest_type == 'ivr_menu':
            from apps.ivr_menus.models import IvrMenu
            ivr = _pl_get('ivr_menus', target) or IvrMenu.objects.get(ivr_menu_uuid=target)
            return [('transfer', f'{ivr.ivr_menu_extension} XML {ctx}')]
        elif dest_type == 'conference':
            from apps.conferences.models import ConferenceProfile
            conf = _pl_get('conferences', target) or ConferenceProfile.objects.get(conference_profile_uuid=target)
            return [('answer', ''), ('conference', conf.conference_profile_name)]
        elif dest_type == 'working_hours':
            from apps.working_hours.models import WorkingHours
            wh = _pl_get('working_hours', target) or WorkingHours.objects.get(working_hours_uuid=target)
            return [('transfer', f'{wh.dialplan_extension} XML {ctx}')]
        elif dest_type == 'external' and external:
            gw = _get_default_gateway(domain_name)
            if gw:
                return [('bridge', f'sofia/gateway/{gw}/{external}')]
            else:
                logger.warning(f"Domain {domain_name} has no default gateway for external transfer.")
                return [('hangup', 'NORMAL_TEMPORARY_FAILURE')]
        elif dest_type == 'hangup':
            return [('hangup', 'NORMAL_CLEARING')]
    except Exception:
        pass
    return [('hangup', 'NORMAL_CLEARING')]


def _call_parking_slot_to_dialplan_xml(slot_obj, domain_name, tenant_code):
    """Generate a single FreeSWITCH <extension> element for one CallParkingSlot.

    Dial SLOT_NUMBER-TENANT_CODE (e.g. 7100-IHS) to park or retrieve.
    BLF hint is park+7100-IHS@domain — unique per tenant.
    valet_park parks when empty, retrieves when occupied.
    """
    tc_suffix = f'-{tenant_code}' if tenant_code else ''
    slot_num = slot_obj.slot_number
    slot_ext = f'{slot_num}{tc_suffix}'
    # Use 'park' as the lot_id so FreeSWITCH presence events fire as
    # park+{slot_ext}@{domain_name}, matching the hint and phone BLF subscription.
    # slot_ext includes the tenant suffix (e.g. 7200-IHS) for multi-tenant isolation.
    moh = slot_obj.music_on_hold or '$${hold_music}'
    timeout = slot_obj.parking_timeout or 60

    hint_el = etree.Element('extension', name=f'park_{slot_ext}',
                            attrib={'hint': f'park+{slot_ext}@{domain_name}'})
    cond = etree.SubElement(hint_el, 'condition',
                            field='destination_number',
                            expression=f'^(park\\+)?({re.escape(slot_ext)}|{slot_num})$')
    etree.SubElement(cond, 'action', application='export', data=f'presence_id=park+{slot_ext}@{domain_name}')
    etree.SubElement(cond, 'action', application='set', data=f'valet_hold_music={moh}')
    etree.SubElement(cond, 'action', application='set', data=f'valet_park_timeout={timeout}')

    if slot_obj.timeout_action == 'return_to_parker':
        etree.SubElement(cond, 'action', application='set',
                         data='valet_park_return_to_parker=true')
    elif slot_obj.timeout_action == 'voicemail' and slot_obj.timeout_voicemail_extension:
        etree.SubElement(cond, 'action', application='set',
                         data='valet_park_timeout_app=voicemail')
        etree.SubElement(cond, 'action', application='set',
                         data=f'valet_park_timeout_data=default {domain_name} {slot_obj.timeout_voicemail_extension}')

    etree.SubElement(cond, 'action', application='valet_park',
                     data=f'valet_parking_lot@{domain_name} {slot_ext}')
    return hint_el


def _ring_group_to_dialplan_xml(rg, domain_name, ctx, preload=None):
    """Generate a FreeSWITCH <extension> element for a ring group.

    Strategies:
      - simultaneous: bridge all destinations at once (separate with :)
      - sequence/rollover: bridge destinations one at a time using loopback legs
      - enterprise: bridge all but continue to next on no-answer per destination timeout
    """
    rg_el = etree.Element('extension', name=f'rg_{rg.ring_group_extension}')
    cond = etree.SubElement(rg_el, 'condition',
                            field='destination_number',
                            expression=f'^{re.escape(rg.ring_group_extension)}$')

    if rg.ring_group_cid_name_prefix:
        etree.SubElement(cond, 'action', application='set',
                         data=f'effective_caller_id_name={rg.ring_group_cid_name_prefix}${{caller_id_name}}')

    if rg.ring_group_cid_number_prefix:
        etree.SubElement(cond, 'action', application='set',
                         data=f'effective_caller_id_number={rg.ring_group_cid_number_prefix}${{caller_id_number}}')

    if rg.ring_group_caller_id_name:
        etree.SubElement(cond, 'action', application='set',
                         data=f'effective_caller_id_name={rg.ring_group_caller_id_name}')

    if rg.ring_group_caller_id_number:
        etree.SubElement(cond, 'action', application='set',
                         data=f'effective_caller_id_number={rg.ring_group_caller_id_number}')

    etree.SubElement(cond, 'action', application='set', data='hangup_after_bridge=true')
    etree.SubElement(cond, 'action', application='set',
                     data='continue_on_fail=USER_BUSY,NO_ANSWER,NO_ROUTE_DESTINATION,ALLOTTED_TIMEOUT,CALL_REJECTED,NORMAL_TEMPORARY_FAILURE,SUBSCRIBER_ABSENT,USER_NOT_REGISTERED,NO_USER_RESPONSE')
    etree.SubElement(cond, 'action', application='set', data='ignore_early_media=true')
    etree.SubElement(cond, 'action', application='set', data='ringback=${us-ring}')
    etree.SubElement(cond, 'action', application='set', data='transfer_ringback=${us-ring}')

    if not rg.ring_group_allow_redirect:
        etree.SubElement(cond, 'action', application='set', data='outbound_redirect_fatal=true')

    call_timeout = rg.ring_group_call_timeout or 60
    destinations = list(rg.destinations.all())
    tenant_code = rg.tenant.tenant_code if rg.tenant else None

    strategy = rg.ring_group_strategy

    if strategy in ('simultaneous', 'enterprise') or not destinations:
        # Use sofia_contact(*/...) so every registered device for each member rings —
        # critical when an extension is registered on multiple endpoints (e.g. desk
        # phone + softphone). user/ only rings the most recent registration.
        legs = []
        for dest in destinations:
            number = dest.destination_number
            delay = dest.destination_delay or 0
            timeout = dest.destination_timeout or call_timeout

            leg_vars = []
            if delay > 0:
                leg_vars.append(f'leg_delay_start={delay}')
            if timeout and timeout != call_timeout:
                leg_vars.append(f'leg_timeout={timeout}')

            leg_prefix = f"[{','.join(leg_vars)}]" if leg_vars else ""

            if re.match(r'^\d{2,10}$', number):
                sip_user = f'{number}-{tenant_code}' if tenant_code else number
                if rg.ring_group_allow_fmfm:
                    ctx_name = f'default-{tenant_code}' if tenant_code else 'default'
                    legs.append(f'{leg_prefix}loopback/{number}/{ctx_name}')
                else:
                    legs.append(f'{leg_prefix}${{sofia_contact(*/{sip_user}@{domain_name})}}')
            else:
                gw = _get_default_gateway(domain_name)
                if gw:
                    legs.append(f'{leg_prefix}sofia/gateway/{gw}/{number}')
                else:
                    logger.warning(f"Domain {domain_name} has no default gateway for Ring Group destination {number}.")

        etree.SubElement(cond, 'action', application='set', data=f'call_timeout={call_timeout}')
        
        if strategy == 'enterprise':
            separator = ':_:' if not rg.ring_group_fast_dial else ','
        else:
            separator = ','
            
        bridge_str = separator.join(legs) if legs else ''
        if bridge_str:
            _add_recording_actions(cond, domain_name)
            etree.SubElement(cond, 'action', application='bridge', data=bridge_str)

    else:
        # sequence/rollover: bridge one at a time, set call_timeout before each bridge
        for dest in destinations:
            number = dest.destination_number
            dest_timeout = dest.destination_timeout or call_timeout
            if re.match(r'^\d{2,10}$', number):
                sip_user = f'{number}-{tenant_code}' if tenant_code else number
                if rg.ring_group_allow_fmfm:
                    ctx_name = f'default-{tenant_code}' if tenant_code else 'default'
                    leg = f'loopback/{number}/{ctx_name}'
                else:
                    leg = f'user/{sip_user}@{domain_name}'
            else:
                gw = _get_default_gateway(domain_name)
                if gw:
                    leg = f'sofia/gateway/{gw}/{number}'
                else:
                    logger.warning(f"Domain {domain_name} has no default gateway for Ring Group destination {number}.")
                    leg = 'error/no_gateway'
            etree.SubElement(cond, 'action', application='set', data=f'call_timeout={dest_timeout}')
            _add_recording_actions(cond, domain_name)
            etree.SubElement(cond, 'action', application='bridge', data=leg)

    # Timeout destination
    # Reset call_timeout so subsequent/timeout destinations do not inherit the short ringgroup timeout
    etree.SubElement(cond, 'action', application='set', data='call_timeout=_undef_')

    timeout_actions = []
    timeout_type = rg.ring_group_timeout_type
    timeout_target = rg.ring_group_timeout_target_uuid
    timeout_external = rg.ring_group_timeout_external_number

    def _pl_get(key, uuid):
        if preload is not None:
            return preload[key].get(str(uuid))
        return None

    try:
        if timeout_type == 'extension':
            from apps.extensions.models import Extension
            ext = _pl_get('extensions', timeout_target) or Extension.objects.get(extension_uuid=timeout_target)
            timeout_actions = [('transfer', f'{ext.extension} XML {ctx}')]
        elif timeout_type == 'ring_group':
            from apps.ring_groups.models import RingGroup
            target_rg = _pl_get('ring_groups', timeout_target) or RingGroup.objects.get(ring_group_uuid=timeout_target)
            timeout_actions = [('transfer', f'{target_rg.ring_group_extension} XML {ctx}')]
        elif timeout_type == 'voicemail':
            from apps.voicemails.models import Voicemail as VoicemailModel
            vm = _pl_get('voicemails', timeout_target) or VoicemailModel.objects.get(voicemail_uuid=timeout_target)
            # Go straight to voicemail actions (TTS, recording, etc.) 
            # instead of transferring back to the extension dialplan.
            _add_voicemail_actions(cond, domain_name, vm.voicemail_id, vm)
            return rg_el
        elif timeout_type == 'ivr_menu':
            from apps.ivr_menus.models import IvrMenu
            ivr = _pl_get('ivr_menus', timeout_target) or IvrMenu.objects.get(ivr_menu_uuid=timeout_target)
            timeout_actions = [('transfer', f'{ivr.ivr_menu_extension} XML {ctx}')]
        elif timeout_type in ('external', 'number', 'call_forward') and timeout_external:
            gw = _get_default_gateway(domain_name)
            if gw:
                digits = re.sub(r'\D', '', timeout_external)
                if timeout_external.strip().startswith('+'):
                    dial_number = '+' + digits
                elif len(digits) == 10:
                    dial_number = '+1' + digits
                elif len(digits) == 11 and digits.startswith('1'):
                    dial_number = '+' + digits
                else:
                    dial_number = digits or timeout_external
                timeout_actions = [('bridge', f'sofia/gateway/{gw}/{dial_number}')]
            else:
                logger.warning(
                    f"Ring group {rg.ring_group_extension}: no default gateway for "
                    f"timeout forward to {timeout_external} on domain {domain_name}."
                )
        elif timeout_type == 'hangup':
            timeout_actions = [('hangup', 'NORMAL_CLEARING')]
    except Exception:
        pass

    if not timeout_actions:
        timeout_actions = [('hangup', 'NORMAL_CLEARING')]

    for app, data in timeout_actions:
        etree.SubElement(cond, 'action', application=app, data=data)

    return rg_el


def _time_condition_to_dialplan_xml(tc, domain_name, tenant_code, preload=None):
    """Generate a FreeSWITCH <extension> element for a TimeCondition.

    Matches the dialplan_extension and evaluates ranges in order.
    Ranges use FreeSWITCH condition attributes (wday, hour, etc.).
    """
    ext_re = re.escape(tc.dialplan_extension)

    tc_el = etree.Element('extension', name=f'tc_{tc.dialplan_extension}')
    # Match the dialled extension
    cond_num = etree.SubElement(tc_el, 'condition', field='destination_number', expression=f'^{ext_re}$')
    cond_num.set('break', 'on-false')

    # Evaluate ranges in order
    ranges = tc.ranges.filter(time_condition_enabled=True).order_by('time_condition_order')
    for r in ranges:
        attrs = {}
        field_map = {
            'time_condition_year': 'year',
            'time_condition_yday': 'yday',
            'time_condition_mon': 'mon',
            'time_condition_mday': 'mday',
            'time_condition_week': 'week',
            'time_condition_mweek': 'mweek',
            'time_condition_wday': 'wday',
            'time_condition_hour': 'hour',
            'time_condition_minute': 'minute',
            'time_condition_minute_of_day': 'minute-of-day',
            'time_condition_time_of_day': 'time-of-day',
            'time_condition_date_time': 'date-time',
        }
        for model_field, fs_attr in field_map.items():
            val = getattr(r, model_field, '')
            if val:
                attrs[fs_attr] = str(val)

        # Create the condition for this range
        range_cond = etree.SubElement(tc_el, 'condition', **attrs)
        # If this range matches, execute action and stop evaluating subsequent ranges
        range_cond.set('break', 'on-true')

        if r.time_condition_destination_app:
            etree.SubElement(range_cond, 'action',
                             application=r.time_condition_destination_app,
                             data=r.time_condition_destination_param or '')

    return tc_el


def _working_hours_to_dialplan_xml(wh, domain_name, tenant_code, preload=None):
    """Generate a list of FreeSWITCH <extension> elements for a WorkingHours profile.

    Produces up to three extensions in order:
      1. wh_{ext}_holiday  (continue=true) — transfers to closed dest on holiday dates
      2. wh_{ext}_schedule (continue=true) — sets wh_open=true for each open time window
      3. wh_{ext}_route               — transfers to open or closed dest based on wh_open flag
    """
    ctx = f'default-{tenant_code}' if tenant_code else 'default'
    ext_re = re.escape(wh.dialplan_extension)
    elements = []

    # Use a unique variable per WorkingHours profile to avoid collision on transfers
    wh_var = f'wh_open_{wh.working_hours_uuid.hex[:8]}'

    # ── 1. Holiday extension ──────────────────────────────────────────────
    holidays = list(wh.holidays.all())
    if holidays:
        holiday_dates = [str(h.holiday_date) for h in holidays]
        holiday_regex = '^(' + '|'.join(re.escape(d) for d in holiday_dates) + ')$'

        ext_hol = etree.Element('extension', name=f'wh_{wh.dialplan_extension}_holiday')
        ext_hol.set('continue', 'true')

        cond_num = etree.SubElement(ext_hol, 'condition',
                                    field='destination_number',
                                    expression=f'^{ext_re}$')
        cond_num.set('break', 'on-false')

        cond_date = etree.SubElement(ext_hol, 'condition',
                                     field='${strftime(%Y-%m-%d)}',
                                     expression=holiday_regex)
        etree.SubElement(cond_date, 'action', application='log', data=f'INFO Working Hours: {wh.working_hours_name} matched HOLIDAY')
        for app, data in _resolve_wh_dest(wh, 'closed', domain_name, ctx, preload=preload):
            etree.SubElement(cond_date, 'action', application=app, data=data)

        elements.append(ext_hol)

    # ── 2 & 3. Single routing extension ───────────────────────────────────
    # NOTE: FreeSWITCH evaluates ALL extension conditions during a single
    # planning phase, THEN executes actions. A two-extension approach
    # (schedule sets a flag, route reads it) does NOT work because the flag
    # is always empty at read time. Instead, each open window has
    # break="on-true" and directly executes the open destination.
    # If no window matches, the call falls through to the closed fallback.
    open_days = [d for d in wh.days.all() if d.is_open and d.open_time and d.close_time]

    ext_route = etree.Element('extension', name=f'wh_{wh.dialplan_extension}_route')

    # Gate: only handle calls to this WH dialplan extension
    cond_gate = etree.SubElement(ext_route, 'condition',
                                  field='destination_number',
                                  expression=f'^{ext_re}$')
    cond_gate.set('break', 'on-false')
    etree.SubElement(cond_gate, 'action', application='log',
                      data=f'DEBUG Working Hours: Evaluating {wh.working_hours_name}. '
                           f'FS Time: ${{strftime(%H:%M)}} FS Wday: ${{strftime(%w)}}')

    # Resolve destinations once
    open_actions   = _resolve_wh_dest(wh, 'open',   domain_name, ctx, preload=preload)
    closed_actions = _resolve_wh_dest(wh, 'closed', domain_name, ctx, preload=preload)

    for day in open_days:
        open_t, open_offset   = _convert_time_to_server_tz(day.open_time,  wh.timezone)
        close_t, close_offset = _convert_time_to_server_tz(day.close_time, wh.timezone)
        
        print(f"INFO: Generation WH {wh.working_hours_name} Day {day.day_of_week}: {day.open_time} -> {open_t} UTC")

        # day_of_week: DB stores 1=Mon...7=Sun; strftime(%w) uses 0=Sun,1=Mon...6=Sat
        fs_wday    = 0 if day.day_of_week == 7 else day.day_of_week
        open_wday  = (fs_wday + open_offset)  % 7
        close_wday = (fs_wday + close_offset) % 7

        # time-of-day attribute only accepts HH:MM (no seconds).
        # Split midnight-crossing UTC ranges into two windows.
        windows = []
        if open_t > close_t:
            windows.append((open_wday,  f'{open_t.strftime("%H:%M")}-23:59'))
            windows.append((close_wday, f'00:00-{close_t.strftime("%H:%M")}'))
        else:
            windows.append((open_wday, f'{open_t.strftime("%H:%M")}-{close_t.strftime("%H:%M")}'))

        for wday_num, tod in windows:
            # FreeSWITCH wday attribute: 1=Sun, 2=Mon ... 7=Sat
            # Our wday_num is 0=Sun, 1=Mon ... 6=Sat
            fs_attr_wday = wday_num + 1
            
            cw = etree.SubElement(ext_route, 'condition')
            cw.set('wday', str(fs_attr_wday))
            cw.set('time-of-day', tod)
            # break="on-true": if BOTH wday and time-of-day match, execute actions and STOP.
            cw.set('break', 'on-true')
            
            etree.SubElement(cw, 'action', application='log',
                              data=f'INFO Working Hours: {wh.working_hours_name} OPEN '
                                   f'(wday={fs_attr_wday} tod={tod})')
            for app, data in open_actions:
                etree.SubElement(cw, 'action', application=app, data=data)

    # Fallback: no open window matched -> closed destination
    cond_closed = etree.SubElement(ext_route, 'condition',
                                    field='destination_number',
                                    expression=f'^{ext_re}$')
    cond_closed.set('break', 'never')
    etree.SubElement(cond_closed, 'action', application='log',
                      data=f'INFO Working Hours: {wh.working_hours_name} CLOSED (no window matched)')
    for app, data in closed_actions:
        etree.SubElement(cond_closed, 'action', application=app, data=data)

    elements.append(ext_route)
    return elements




def _resolve_cf_dest(cf, when, domain_name, ctx, preload=None):
    """Resolve a CallFlow day/night destination to (app, data) tuples."""
    if when == 'day':
        dest_type = cf.day_dest_type
        target = cf.day_dest_target_uuid
        external = cf.day_dest_external_number
    else:
        dest_type = cf.night_dest_type
        target = cf.night_dest_target_uuid
        external = cf.night_dest_external_number

    if not dest_type:
        return [('hangup', 'NORMAL_CLEARING')]

    def _pl_get(key, uuid):
        if preload is not None:
            return preload[key].get(str(uuid))
        return None

    if dest_type == 'extension':
        from apps.extensions.models import Extension
        ext = _pl_get('extensions', target) or Extension.objects.get(extension_uuid=target)
        return [('transfer', f'{ext.extension} XML {ctx}')]
    elif dest_type == 'ring_group':
        from apps.ring_groups.models import RingGroup
        rg = _pl_get('ring_groups', target) or RingGroup.objects.get(ring_group_uuid=target)
        return [('transfer', f'{rg.ring_group_extension} XML {ctx}')]
    elif dest_type == 'voicemail':
        from apps.extensions.models import Extension
        ext = _pl_get('extensions', target) or Extension.objects.get(extension_uuid=target)
        return [('answer', ''), ('sleep', '1000'), ('voicemail', f'default {domain_name} {ext.extension}')]
    elif dest_type == 'ivr_menu':
        from apps.ivr_menus.models import IvrMenu
        ivr = _pl_get('ivr_menus', target) or IvrMenu.objects.get(ivr_menu_uuid=target)
        return [('transfer', f'{ivr.ivr_menu_extension} XML {ctx}')]
    elif dest_type == 'conference':
        from apps.conferences.models import ConferenceProfile
        conf = _pl_get('conferences', target) or ConferenceProfile.objects.get(conference_profile_uuid=target)
        return [('answer', ''), ('conference', conf.conference_profile_name)]
    elif dest_type == 'working_hours':
        from apps.working_hours.models import WorkingHours
        wh = _pl_get('working_hours', target) or WorkingHours.objects.get(working_hours_uuid=target)
        return [('transfer', f'{wh.dialplan_extension} XML {ctx}')]
    elif dest_type == 'external':
        if external:
            gw = _get_default_gateway(domain_name)
            return [('bridge', f'sofia/gateway/{gw}/{external}')]
    elif dest_type == 'hangup':
        return [('hangup', 'NORMAL_CLEARING')]

    return [('hangup', 'NORMAL_CLEARING')]


def generate_dialplan_xml(domain_name, destination_number, caller_id_number='', caller_id_name=''):
    """
    Generate dialplan XML for FreeSWITCH.

    Builds three layers in order (FreeSWITCH uses the first matching rule):
      1. public  context — auto-generated from Destination records (inbound DIDs)
      2. any     context — manual Dialplan records (admin-managed raw XML)
      3. default context — auto-generated from Extension records (local routing)
    """
    from apps.dialplans.models import Dialplan
    from apps.destinations.models import Destination

    domain = _resolve_domain(domain_name)
    if domain is None:
        # External profile sends hostname (e.g. "freeswitch") instead of SIP domain.
        # Fall back to the first enabled domain so inbound DID routing still works.
        from core.models import Domain
        domain = Domain.objects.filter(domain_enabled=True).order_by('domain_name').first()
    if domain is None:
        return not_found_xml()

    # Always use the domain's actual SIP domain name for bridge/voicemail strings,
    # not the hostname that FreeSWITCH sent in the request.
    domain_name = domain.domain_name

    # ── Bulk-fetch all domain objects to eliminate N+1 queries ───────────
    # Each resolve function previously called .objects.get() per destination;
    # now they do a dict lookup into these preloaded maps instead.
    from apps.extensions.models import Extension as _Ext
    from apps.ivr_menus.models import IvrMenu as _IvrMenu
    from apps.ring_groups.models import RingGroup as _RingGroup
    from apps.time_conditions.models import TimeCondition as _TimeCondition
    from apps.working_hours.models import WorkingHours as _WorkingHours
    from apps.call_flows.models import CallFlow as _CallFlow
    from apps.conferences.models import ConferenceProfile as _ConferenceProfile
    from apps.custom_destinations.models import CustomDestination as _CustomDestination
    from apps.call_parking.models import CallParkingSlot as _CallParkingSlot
    from apps.voicemails.models import Voicemail as _Voicemail

    _ext_qs = list(_Ext.objects.select_related('tenant').filter(domain=domain, enabled=True))

    preload = {
        'extensions':      {str(e.extension_uuid): e   for e in _ext_qs},
        'ivr_menus':       {str(o.ivr_menu_uuid): o    for o in _IvrMenu.objects.select_related('tenant').prefetch_related('options').filter(domain=domain, ivr_menu_enabled=True)},
        'ring_groups':     {str(o.ring_group_uuid): o  for o in _RingGroup.objects.select_related('tenant').prefetch_related('destinations').filter(domain=domain, ring_group_enabled=True)},
        'voicemails':      {str(o.voicemail_uuid): o   for o in _Voicemail.objects.filter(domain=domain, voicemail_enabled=True)},
        'time_conditions': {str(o.dialplan_uuid): o    for o in _TimeCondition.objects.select_related('tenant').filter(domain=domain, dialplan_enabled=True)},
        'working_hours':   {str(o.working_hours_uuid): o for o in _WorkingHours.objects.select_related('tenant').prefetch_related('days', 'holidays').filter(domain=domain, working_hours_enabled=True)},
        'call_flows':      {str(o.call_flow_uuid): o   for o in _CallFlow.objects.select_related('tenant').filter(domain=domain, call_flow_enabled=True)},
        'conferences':     {str(o.conference_profile_uuid): o for o in _ConferenceProfile.objects.select_related('tenant').filter(domain=domain)},
        'custom_dests':    {str(o.custom_destination_uuid): o for o in _CustomDestination.objects.filter(domain=domain)},
        'parking_slots':   {str(o.call_parking_slot_uuid): o  for o in _CallParkingSlot.objects.select_related('tenant', 'domain').filter(domain=domain, slot_enabled=True)},
    }

    root = etree.Element('document', type='freeswitch/xml')
    section = etree.SubElement(root, 'section', name='dialplan', description='Dialplan')

    logger.info(f"Generating dialplan for domain: {domain.domain_name} (uuid: {domain.domain_uuid})")

    def get_or_create_context(name):
        ctx = section.find(f'.//context[@name="{name}"]')
        if ctx is None:
            ctx = etree.SubElement(section, 'context', name=name)
        return ctx

    # ── 1. public context: inbound DIDs from ALL enabled Destination records ──
    # Carriers often send calls to the server IP or a generic hostname, bypassing
    # our domain resolution. To ensure DIDs always work, we include all enabled
    # destinations from all domains in the 'public' context.
    dests = list(Destination.objects.select_related('domain', 'tenant').filter(
        destination_enabled=True,
    ).order_by('destination_number'))

    logger.info(f"Generating global public context with {len(dests)} destinations.")

    for dest in dests:
        # Use the destination's own domain name for routing if available;
        # otherwise fall back to the requested domain_name.
        d_domain_name = dest.domain.domain_name if dest.domain else domain_name
        get_or_create_context('public').append(
            _destination_to_extension_xml(dest, d_domain_name, caller_id_number=caller_id_number, preload=preload)
        )

    # ── 2. Manual Dialplan records (any context, ordered by dialplan_order) ─
    for dp in Dialplan.objects.filter(
        domain=domain,
        dialplan_enabled=True,
    ).order_by('dialplan_order'):
        if dp.dialplan_xml:
            try:
                get_or_create_context(dp.dialplan_context or 'default').append(
                    etree.fromstring(dp.dialplan_xml.encode())
                )
            except Exception:
                logger.warning('Invalid dialplan XML for %s (%s)', dp.dialplan_name, dp.dialplan_uuid)

    # ── 3. Per-tenant contexts: each tenant's extensions are isolated ─────
    # Context name: default-{tenant_code} (e.g. default-IHS).
    # user_context in the directory is set to the same value, so calls
    # from one tenant cannot reach extensions in another tenant's context.

    # 3a. Outbound routes — matched first, before local extensions.
    # Tenant-specific routes go into that tenant's context only.
    # Shared routes (no tenant, no domain or domain-matched) go into every
    # tenant context so new tenants can reuse shared gateways.
    from apps.outbound_routes.models import OutboundRoute
    all_tenant_codes = list({
        e.tenant.tenant_code
        for e in _ext_qs
        if e.tenant_id is not None
    })
    for route in OutboundRoute.objects.select_related(
        'tenant', 'gateway', 'gateway_2', 'gateway_3'
    ).filter(
        outbound_route_enabled=True,
    ).filter(
        models.Q(domain=domain) | models.Q(domain__isnull=True)
    ).order_by(
        'outbound_route_order', 'outbound_route_name'
    ):
        if route.tenant_id:
            # Tenant-specific — only goes into that tenant's context
            ctx_name = f'default-{route.tenant.tenant_code}'
            get_or_create_context(ctx_name).append(_outbound_route_to_xml(route))
        else:
            # Shared/global — add to every tenant context and bare 'default'
            get_or_create_context('default').append(_outbound_route_to_xml(route))
            for tc in all_tenant_codes:
                get_or_create_context(f'default-{tc}').append(_outbound_route_to_xml(route))

    # 3b. Local extension routing
    # Pre-fetch voicemail boxes for greeting style lookup (avoids N+1)
    from apps.voicemails.models import Voicemail as VoicemailModel
    dialplan_vm_map = {
        (vm.tenant_id, vm.voicemail_id): vm
        for vm in VoicemailModel.objects.filter(domain=domain, voicemail_enabled=True)
    }
    for ext in sorted(_ext_qs, key=lambda e: e.extension):
        mailbox_id = ext.voicemail_id or ext.extension
        vm = dialplan_vm_map.get((ext.tenant_id, mailbox_id))
        tenant_code = ext.tenant.tenant_code if ext.tenant else None
        ctx_name = f'default-{tenant_code}' if tenant_code else 'default'
        ctx = get_or_create_context(ctx_name)
        for ext_el in _extension_to_dialplan_xml(ext, domain_name, vm=vm):
            ctx.append(ext_el)

    # ── 4. Voicemail access rules in each tenant context ─────────────────
    # *98 → caller checks their own mailbox
    # *97 → caller enters a mailbox number to check
    seen_contexts = set()
    for ext in _ext_qs:
        tenant_code = ext.tenant.tenant_code if ext.tenant else None
        ctx_name = f'default-{tenant_code}' if tenant_code else 'default'
        if ctx_name in seen_contexts:
            continue
        seen_contexts.add(ctx_name)
        ctx = get_or_create_context(ctx_name)

        # *98 — check own voicemail
        vm_self = etree.SubElement(ctx, 'extension', name='voicemail_self')
        vm_self_cond = etree.SubElement(vm_self, 'condition',
                                        field='destination_number', expression=r'^\*98$')
        etree.SubElement(vm_self_cond, 'action', application='answer')
        etree.SubElement(vm_self_cond, 'action', application='sleep', data='1000')
        # ${voicemail_id} is set per-user in the directory, so *98 always
        # opens the correct mailbox even when voicemail_id != extension number.
        etree.SubElement(vm_self_cond, 'action', application='voicemail',
                         data=f'check default {domain_name} ${{voicemail_id}}')

        # *97 — check any mailbox by number
        vm_any = etree.SubElement(ctx, 'extension', name='voicemail_other')
        vm_any_cond = etree.SubElement(vm_any, 'condition',
                                       field='destination_number', expression=r'^\*97$')
        etree.SubElement(vm_any_cond, 'action', application='answer')
        etree.SubElement(vm_any_cond, 'action', application='sleep', data='1000')
        etree.SubElement(vm_any_cond, 'action', application='voicemail',
                         data=f'check default {domain_name}')

        # *95 — record own voicemail name greeting
        vm_rec = etree.SubElement(ctx, 'extension', name='voicemail_record_name')
        vm_rec_cond = etree.SubElement(vm_rec, 'condition',
                                       field='destination_number', expression=r'^\*95$')
        etree.SubElement(vm_rec_cond, 'action', application='answer')
        etree.SubElement(vm_rec_cond, 'action', application='sleep', data='1000')
        etree.SubElement(vm_rec_cond, 'action', application='playback',
                         data='tone_stream://%(500,0,640)')
        etree.SubElement(vm_rec_cond, 'action', application='record',
                         data=f'/var/lib/freeswitch/storage/voicemail/default/{domain_name}/${{voicemail_id}}/recorded_name.wav 10 200 3')
        etree.SubElement(vm_rec_cond, 'action', application='playback',
                         data='ivr/ivr-recording_saved.wav')
        etree.SubElement(vm_rec_cond, 'action', application='hangup')

        # ── Eavesdrop feature codes ──────────────────────────────────────
        # *33<ext> — listen only  (supervisor hears both legs, muted)
        # *34<ext> — whisper mode (supervisor can speak to called party only)
        # *35<ext> — barge in     (full three-way, both legs hear supervisor)
        #
        # When FreeSWITCH originates to eavesdrop_bridge XML <ctx>,
        # the eavesdrop_uuid channel var is already set on the channel,
        # so the dialplan simply reads it and passes it to the app.
        #
        # Direct-dial variants (*33XXXX) look up the UUID via sofia_contact
        # so a supervisor can also dial from their physical phone.
        for code, flags, name in (
            (r'^\*33(\d+)$', 'r',  'eavesdrop_listen'),
            (r'^\*34(\d+)$', 'w',  'eavesdrop_whisper'),
            (r'^\*35(\d+)$', 'rw', 'eavesdrop_barge'),
        ):
            ev_ext = etree.SubElement(ctx, 'extension', name=name)
            ev_cond = etree.SubElement(ev_ext, 'condition',
                                       field='destination_number', expression=code)
            etree.SubElement(ev_cond, 'action', application='answer')
            etree.SubElement(ev_cond, 'action', application='sleep', data='500')
            etree.SubElement(ev_cond, 'action', application='set',
                             data=f'eavesdrop_flags={flags}')
            # Use the eavesdrop_uuid var if set (via originate from UI),
            # otherwise fall back to cycling through all channels
            etree.SubElement(ev_cond, 'action', application='eavesdrop',
                             data='${eavesdrop_uuid}')

        # eavesdrop_bridge — landing extension when UI originates eavesdrop call
        # The originate command sets eavesdrop_uuid + eavesdrop_flags on the channel.
        ev_bridge = etree.SubElement(ctx, 'extension', name='eavesdrop_bridge')
        ev_bridge_cond = etree.SubElement(ev_bridge, 'condition',
                                           field='destination_number',
                                           expression=r'^eavesdrop_bridge$')
        etree.SubElement(ev_bridge_cond, 'action', application='answer')
        etree.SubElement(ev_bridge_cond, 'action', application='sleep', data='500')
        etree.SubElement(ev_bridge_cond, 'action', application='eavesdrop',
                         data='${eavesdrop_uuid}')

    # ── 5. rxfax receive extensions for each enabled Fax box ──────────────
    # Each Fax box gets a rxfax_<extension> extension in its tenant's context.
    # CNG-enabled DIDs and fax-only DIDs both transfer here when fax is detected.
    from apps.fax.models import Fax
    for fax in Fax.objects.select_related('tenant').filter(domain=domain, fax_enabled=True):
        tenant_code = fax.tenant.tenant_code if fax.tenant else None
        ctx_name = f'default-{tenant_code}' if tenant_code else 'public'
        get_or_create_context(ctx_name).append(
            _fax_receive_extension_xml(fax, domain_name)
        )

    # ── 6. Working hours extensions in each tenant context ────────────────
    # Each enabled WorkingHours profile generates up to three <extension> elements:
    #   wh_{ext}_holiday  — redirect to closed dest on holiday dates
    #   wh_{ext}_schedule — set wh_open=true flag for matching time windows
    #   wh_{ext}_route    — route to open or closed dest based on flag
    for wh in preload['working_hours'].values():
        tenant_code = wh.tenant.tenant_code if wh.tenant else None
        ctx_name = f'default-{tenant_code}' if tenant_code else 'default'
        for ext_el in _working_hours_to_dialplan_xml(wh, domain_name, tenant_code, preload=preload):
            get_or_create_context(ctx_name).append(ext_el)

    # ── 6b. Time conditions (Working Conditions) ───────────────────────────
    for tc in preload['time_conditions'].values():
        tenant_code = tc.tenant.tenant_code if tc.tenant else None
        ctx_name = f'default-{tenant_code}' if tenant_code else 'default'
        get_or_create_context(ctx_name).append(
            _time_condition_to_dialplan_xml(tc, domain_name, tenant_code, preload=preload)
        )

    # ── 7. Ring group extensions in each tenant context ───────────────────
    for rg in preload['ring_groups'].values():
        tenant_code = rg.tenant.tenant_code if rg.tenant else None
        ctx_name = f'default-{tenant_code}' if tenant_code else 'default'
        rg_domain_name = rg.domain.domain_name if rg.domain_id else domain_name
        get_or_create_context(ctx_name).append(
            _ring_group_to_dialplan_xml(rg, rg_domain_name, ctx_name, preload=preload)
        )

    # ── 8. IVR menu extensions in each tenant context ─────────────────────
    for ivr in preload['ivr_menus'].values():
        if not ivr.ivr_menu_extension:
            continue  # legacy record with no extension — skip until re-saved
        tenant_code = ivr.tenant.tenant_code if ivr.tenant else None
        ctx_name = f'default-{tenant_code}' if tenant_code else 'default'
        ivr_ext_el = etree.Element('extension', name=f'ivr_{ivr.ivr_menu_extension}')
        ivr_cond = etree.SubElement(ivr_ext_el, 'condition',
                                    field='destination_number',
                                    expression=f'^{re.escape(ivr.ivr_menu_extension)}$')
        etree.SubElement(ivr_cond, 'action', application='answer')
        etree.SubElement(ivr_cond, 'action', application='sleep', data='1000')
        etree.SubElement(ivr_cond, 'action', application='ivr',
                         data=str(ivr.ivr_menu_uuid))
        # After mod_ivr_menu exits, transfer to the exit handler extension to evaluate ivr_menu_status
        etree.SubElement(ivr_cond, 'action', application='transfer',
                         data=f'ivr_{ivr.ivr_menu_extension}_exit XML {ctx_name}')
        get_or_create_context(ctx_name).append(ivr_ext_el)

        # 8a. IVR Exit handler extension to evaluate ivr_menu_status
        ivr_exit_el = etree.Element('extension', name=f'ivr_{ivr.ivr_menu_extension}_exit')
        match_cond = etree.SubElement(ivr_exit_el, 'condition',
                                      field='destination_number',
                                      expression=f'^ivr_{re.escape(ivr.ivr_menu_extension)}_exit$')
        match_cond.set('break', 'never')

        # Find specific timeout, invalid (failure), or hangup options
        timeout_opt = None
        invalid_opt = None
        hangup_opt = None
        for opt in ivr.options.all():
            if opt.ivr_menu_option_digits == 'timeout':
                timeout_opt = opt
            elif opt.ivr_menu_option_digits == 'invalid':
                invalid_opt = opt
            elif opt.ivr_menu_option_digits == 'hangup':
                hangup_opt = opt

        if timeout_opt:
            timeout_actions = _resolve_wh_dest_from_type(
                timeout_opt.ivr_menu_option_dest_type,
                timeout_opt.ivr_menu_option_dest_target_uuid,
                timeout_opt.ivr_menu_option_dest_external_number,
                domain_name, ctx_name, preload=preload,
            )
            if timeout_actions:
                timeout_cond = etree.SubElement(ivr_exit_el, 'condition',
                                                field='${ivr_menu_status}',
                                                expression='^timeout$')
                timeout_cond.set('break', 'on-true')
                for app, data in timeout_actions:
                    etree.SubElement(timeout_cond, 'action', application=app, data=data)

        if invalid_opt:
            invalid_actions = _resolve_wh_dest_from_type(
                invalid_opt.ivr_menu_option_dest_type,
                invalid_opt.ivr_menu_option_dest_target_uuid,
                invalid_opt.ivr_menu_option_dest_external_number,
                domain_name, ctx_name, preload=preload,
            )
            if invalid_actions:
                invalid_cond = etree.SubElement(ivr_exit_el, 'condition',
                                                field='${ivr_menu_status}',
                                                expression='^failure$')
                invalid_cond.set('break', 'on-true')
                for app, data in invalid_actions:
                    etree.SubElement(invalid_cond, 'action', application=app, data=data)

        if hangup_opt:
            hangup_actions = _resolve_wh_dest_from_type(
                hangup_opt.ivr_menu_option_dest_type,
                hangup_opt.ivr_menu_option_dest_target_uuid,
                hangup_opt.ivr_menu_option_dest_external_number,
                domain_name, ctx_name, preload=preload,
            )
            if hangup_actions:
                hangup_cond = etree.SubElement(ivr_exit_el, 'condition',
                                               field='${ivr_menu_status}',
                                               expression='^hangup$')
                hangup_cond.set('break', 'on-true')
                for app, data in hangup_actions:
                    etree.SubElement(hangup_cond, 'action', application=app, data=data)

        # Fallback / General Exit Action
        # Reuse the internal-dial-invalid destination as a general "where to go when the IVR gives up" target.
        # Hangup if unset.
        fallback_actions = _resolve_wh_dest_from_type(
            ivr.ivr_menu_internal_dial_invalid_type,
            ivr.ivr_menu_internal_dial_invalid_target_uuid,
            ivr.ivr_menu_internal_dial_invalid_external_number,
            domain_name, ctx_name, preload=preload,
        ) or [('hangup', 'NORMAL_CLEARING')]

        fallback_cond = etree.SubElement(ivr_exit_el, 'condition',
                                         field='destination_number',
                                         expression=f'^ivr_{re.escape(ivr.ivr_menu_extension)}_exit$')
        for app, data in fallback_actions:
            etree.SubElement(fallback_cond, 'action', application=app, data=data)

        get_or_create_context(ctx_name).append(ivr_exit_el)

        # 8b. Direct-dial fallback extension — handles <digits># entered inside
        # the IVR. The IVR conf entry transfers to "ivr_dd_<short><digits>"; we
        # check if <digits> matches an extension in this tenant. If yes,
        # transfer; otherwise execute the configured invalid-fallback action.
        if ivr.ivr_menu_allow_internal_dial:
            short = str(ivr.ivr_menu_uuid).replace('-', '')[:8]
            tenant_exts = [
                e.extension for e in preload['extensions'].values()
                if (e.tenant_id == ivr.tenant_id) and e.extension
            ]
            # 1. Direct-dial match extension: matches destination_number directly if the extension exists.
            if tenant_exts:
                alt = '|'.join(re.escape(e) for e in tenant_exts)
                dd_el = etree.Element('extension', name=f'ivr_dd_{short}')
                match_cond = etree.SubElement(dd_el, 'condition',
                                              field='destination_number',
                                              expression=f'^ivr_dd_{short}({alt})$')
                etree.SubElement(match_cond, 'action', application='transfer',
                                 data=f'$1 XML {ctx_name}')
                get_or_create_context(ctx_name).append(dd_el)

            # 2. Direct-dial fallback extension: matches any other digits dialed inside this IVR direct dial.
            dd_fb_el = etree.Element('extension', name=f'ivr_dd_{short}_fallback')
            fb_cond = etree.SubElement(dd_fb_el, 'condition',
                                       field='destination_number',
                                       expression=f'^ivr_dd_{short}(\\d+)$')
            invalid_actions = _resolve_wh_dest_from_type(
                ivr.ivr_menu_internal_dial_invalid_type,
                ivr.ivr_menu_internal_dial_invalid_target_uuid,
                ivr.ivr_menu_internal_dial_invalid_external_number,
                domain_name, ctx_name, preload=preload,
            ) or [('hangup', 'NORMAL_CLEARING')]
            for app, data in invalid_actions:
                etree.SubElement(fb_cond, 'action', application=app, data=data)
            get_or_create_context(ctx_name).append(dd_fb_el)

    # ── 9. Call flow routing + feature code extensions ────────────────────
    for cf in preload['call_flows'].values():
        tenant_code = cf.tenant.tenant_code if cf.tenant else None
        ctx_name = f'default-{tenant_code}' if tenant_code else 'default'

        # 9a. Routing extension — matches extension number, then checks db() for day/night
        if cf.call_flow_extension:
            cf_ext_el = etree.Element('extension', name=f'cf_{cf.call_flow_extension}')
            # First condition: match the destination number (break=never so we fall through)
            num_cond = etree.SubElement(cf_ext_el, 'condition',
                                        field='destination_number',
                                        expression=f'^{re.escape(cf.call_flow_extension)}$')
            num_cond.set('break', 'never')
            # Second condition: db() == 'true' → day actions, else night anti-actions
            day_cond = etree.SubElement(cf_ext_el, 'condition',
                                        field=f'${{db(select/call_flow/{cf.call_flow_uuid})}}',
                                        expression='^true$')
            if cf.day_dest_type:
                try:
                    for app, data in _resolve_cf_dest(cf, 'day', domain_name, ctx_name, preload=preload):
                        etree.SubElement(day_cond, 'action', application=app, data=data)
                except Exception as e:
                    logger.warning('CallFlow %s day dest error: %s', cf.call_flow_uuid, e)
            if cf.night_dest_type:
                try:
                    for app, data in _resolve_cf_dest(cf, 'night', domain_name, ctx_name, preload=preload):
                        etree.SubElement(day_cond, 'anti-action', application=app, data=data)
                except Exception as e:
                    logger.warning('CallFlow %s night dest error: %s', cf.call_flow_uuid, e)
            get_or_create_context(ctx_name).append(cf_ext_el)

        # 9b. Feature code extension — toggles the call_flow_status and plays a tone
        if cf.call_flow_feature_code:
            fc_el = etree.Element('extension', name=f'cf_toggle_{cf.call_flow_feature_code}')
            fc_cond = etree.SubElement(fc_el, 'condition',
                                       field='destination_number',
                                       expression=f'^{re.escape(cf.call_flow_feature_code)}$')
            etree.SubElement(fc_cond, 'action', application='answer')
            etree.SubElement(fc_cond, 'action', application='sleep', data='500')
            # Toggle: if currently true → set false, else set true
            etree.SubElement(fc_cond, 'action', application='set',
                             data=f'call_flow_uuid={cf.call_flow_uuid}')
            etree.SubElement(fc_cond, 'action', application='execute_extension',
                             data=f'cf_toggle_exec_{cf.call_flow_uuid} XML {ctx_name}')
            etree.SubElement(fc_cond, 'action', application='hangup')
            get_or_create_context(ctx_name).append(fc_el)

            # Internal toggle-exec extension (matched by uuid, not dialled directly)
            tgl_el = etree.Element('extension', name=f'cf_toggle_exec_{cf.call_flow_uuid}')
            # If currently true → play night sound, set false
            tgl_true = etree.SubElement(tgl_el, 'condition',
                                        field=f'${{db(select/call_flow/{cf.call_flow_uuid})}}',
                                        expression='^true$')
            etree.SubElement(tgl_true, 'action', application='db',
                             data=f'insert/call_flow/{cf.call_flow_uuid}/false')
            night_sound = cf.call_flow_sound or 'ivr/ivr-after_hours.wav'
            etree.SubElement(tgl_true, 'action', application='playback', data=night_sound)
            # If currently false → play day sound, set true
            day_sound = cf.call_flow_greeting or 'ivr/ivr-welcome_to_freeswitch.wav'
            etree.SubElement(tgl_true, 'anti-action', application='db',
                             data=f'insert/call_flow/{cf.call_flow_uuid}/true')
            etree.SubElement(tgl_true, 'anti-action', application='playback', data=day_sound)
            get_or_create_context(ctx_name).append(tgl_el)

    # ── 10. Call parking slot extensions ─────────────────────────────────
    for slot_obj in preload['parking_slots'].values():
        tenant_code = slot_obj.tenant.tenant_code if slot_obj.tenant else None
        ctx_name = f'default-{tenant_code}' if tenant_code else 'default'
        slot_domain_name = slot_obj.domain.domain_name
        get_or_create_context(ctx_name).append(
            _call_parking_slot_to_dialplan_xml(slot_obj, slot_domain_name, tenant_code)
        )

    if not len(section):
        return not_found_xml()

    return etree.tostring(root, pretty_print=True, xml_declaration=True, encoding='UTF-8').decode()


def generate_configuration_xml(key_name, domain_name=''):
    """Generate configuration XML for a specific FreeSWITCH module."""
    handlers = {
        # sofia.conf is intentionally excluded — FreeSWITCH loads SIP profile
        # settings from its own static files. Gateways are written as XML files
        # to the sip_profiles/external/ directory by GatewayViewSet and loaded
        # via 'sofia profile external rescan'.
        'voicemail.conf': generate_voicemail_conf,
        'callcenter.conf': generate_callcenter_conf,
        'conference.conf': generate_conference_conf,
        'acl.conf': generate_acl_conf,
        'xml_cdr.conf': generate_xml_cdr_conf,
        'ivr.conf': generate_ivr_conf,
    }
    handler = handlers.get(key_name)
    if handler:
        return handler(domain_name)
    return not_found_xml()


def generate_ivr_conf(domain_name=''):
    """Generate ivr.conf so FreeSWITCH knows all IVR menu definitions."""
    from apps.ivr_menus.models import IvrMenu, IvrMenuOption
    from apps.extensions.models import Extension
    from apps.ring_groups.models import RingGroup
    from apps.voicemails.models import Voicemail
    from apps.working_hours.models import WorkingHours
    from apps.conferences.models import ConferenceProfile
    from apps.custom_destinations.models import CustomDestination

    root = etree.Element('document', type='freeswitch/xml')
    section = etree.SubElement(root, 'section', name='configuration')
    conf = etree.SubElement(section, 'configuration', name='ivr.conf', description='IVR Menus')
    menus_el = etree.SubElement(conf, 'menus')

    # Resolve domain to filter IVRs if possible; fall back to all enabled
    domain = _resolve_domain(domain_name) if domain_name else None
    qs = IvrMenu.objects.select_related('tenant').prefetch_related('options__ivr_menu').filter(
        ivr_menu_enabled=True
    )
    if domain:
        qs = qs.filter(domain=domain)

    from django.conf import settings as _settings
    import os as _os
    sounds_dir = getattr(_settings, 'FREESWITCH_SOUNDS_DIR', '')

    def _resolve_sound(filename):
        """Return a path FreeSWITCH can play. If it's a bare filename, prepend FREESWITCH_SOUNDS_DIR."""
        if not filename:
            return ''
        # Already absolute or a FreeSWITCH stream/built-in (contains / or :)
        if filename.startswith('/') or ':' in filename:
            return filename
        # Bare filename — resolve to full path on disk
        if sounds_dir:
            return _os.path.join(sounds_dir, filename)
        return filename

    for ivr in qs:
        tenant_code = ivr.tenant.tenant_code if ivr.tenant else None
        ctx = f'default-{tenant_code}' if tenant_code else 'default'
        
        # Logging to help diagnose missing options
        option_digits = [o.ivr_menu_option_digits for o in ivr.options.all()]
        logger.info(f"Generating IVR {ivr.ivr_menu_name} ({ivr.ivr_menu_uuid}). Options in DB: {option_digits}")

        menu_attrs = {
            'name': str(ivr.ivr_menu_uuid),
            'greet-long':  _resolve_sound(ivr.ivr_menu_greet_long)  or 'silence_stream://500',
            'greet-short': _resolve_sound(ivr.ivr_menu_greet_short) or 'silence_stream://500',
            'invalid-sound':  _resolve_sound(ivr.ivr_menu_invalid_sound)  or 'ivr/ivr-that_was_an_invalid_entry.wav',
            'exit-sound':     _resolve_sound(ivr.ivr_menu_exit_sound)     or '',
            'timeout':        str(ivr.ivr_menu_timeout),
            'inter-digit-timeout': str(ivr.ivr_menu_inter_digit_timeout),
            'max-failures':   str(ivr.ivr_menu_max_failures),
            'max-timeouts':   str(ivr.ivr_menu_max_timeouts),
            'digit-len':      str(ivr.ivr_menu_digit_len or 1),
            'context':        ctx,
            'direct-dial':    'true' if ivr.ivr_menu_allow_internal_dial else 'false',
        }
        if ivr.ivr_menu_confirm_macro:
            menu_attrs['confirm-macro'] = ivr.ivr_menu_confirm_macro
        if ivr.ivr_menu_confirm_key:
            menu_attrs['confirm-key'] = ivr.ivr_menu_confirm_key
        if ivr.ivr_menu_tts_engine:
            menu_attrs['tts-engine'] = ivr.ivr_menu_tts_engine
        if ivr.ivr_menu_tts_voice:
            menu_attrs['tts-voice'] = ivr.ivr_menu_tts_voice

        menu_el = etree.SubElement(menus_el, 'menu', **menu_attrs)

        # ── IVR Options ───────────────────────────────────────────────────
        for opt in ivr.options.all():
            digits = opt.ivr_menu_option_digits
            if digits in ('timeout', 'invalid', 'hangup'):
                continue
            dest_type = opt.ivr_menu_option_dest_type
            dest_uuid = opt.ivr_menu_option_dest_target_uuid
            external = opt.ivr_menu_option_dest_external_number

            action = None
            param = None

            # First priority: Resolve based on dest_type + dest_uuid
            if dest_type:
                try:
                    if dest_type == 'extension':
                        ext = Extension.objects.get(extension_uuid=dest_uuid)
                        action, param = 'menu-exec-app', f'transfer {ext.extension} XML {ctx}'

                    elif dest_type == 'ivr_menu':
                        sub_ivr = IvrMenu.objects.get(ivr_menu_uuid=dest_uuid)
                        action, param = 'menu-sub', str(sub_ivr.ivr_menu_uuid)

                    elif dest_type == 'ring_group':
                        target_ext = None
                        try:
                            rg = RingGroup.objects.get(ring_group_uuid=dest_uuid)
                            target_ext = rg.ring_group_extension
                        except Exception:
                            ext = Extension.objects.get(extension_uuid=dest_uuid)
                            target_ext = ext.extension
                        if target_ext:
                            action, param = 'menu-exec-app', f'transfer {target_ext} XML {ctx}'

                    elif dest_type == 'voicemail':
                        mailbox_id = None
                        try:
                            vm = Voicemail.objects.get(voicemail_uuid=dest_uuid)
                            mailbox_id = vm.voicemail_id
                        except Exception:
                            ext = Extension.objects.get(extension_uuid=dest_uuid)
                            mailbox_id = ext.extension
                        if mailbox_id:
                            action, param = 'menu-exec-app', f'voicemail default {domain_name} {mailbox_id}'

                    elif dest_type == 'conference':
                        cp = ConferenceProfile.objects.get(conference_profile_uuid=dest_uuid)
                        action, param = 'menu-exec-app', f'conference {cp.conference_profile_name}'

                    elif dest_type in ('external', 'call_forward', 'number') and external:
                        gw = _get_default_gateway(domain_name)
                        if gw:
                            action, param = 'menu-exec-app', f'bridge sofia/gateway/{gw}/{external}'
                        else:
                            logger.warning(f"Domain {domain_name} has no default gateway for IVR external transfer.")

                    elif dest_type == 'working_hours':
                        wh = WorkingHours.objects.get(working_hours_uuid=dest_uuid)
                        action, param = 'menu-exec-app', f'transfer {wh.dialplan_extension} XML {ctx}'

                    elif dest_type == 'custom_destination':
                        cd = CustomDestination.objects.get(custom_destination_uuid=dest_uuid)
                        actions = _resolve_wh_dest_from_type(
                            cd.dest_type, cd.dest_target_uuid, cd.dest_external_number,
                            domain_name, ctx,
                        )
                        if actions:
                            app, data = actions[0]
                            action, param = 'menu-exec-app', f'{app} {data}'.strip()

                    elif dest_type == 'call_flow':
                        from apps.dialplans.models import Dialplan
                        dp = Dialplan.objects.get(dialplan_uuid=dest_uuid)
                        action, param = 'menu-exec-app', f'transfer {dp.dialplan_number} XML {ctx}'

                    elif dest_type == 'hangup':
                        action, param = 'menu-exec-app', 'hangup'
                    
                    elif dest_type in ('internal_dial', 'dial_extension', 'direct_dial'):
                        action, param = 'menu-exec-app', f'transfer $1 XML {ctx}'

                except Exception as e:
                    logger.warning(f"IVR menu {ivr.ivr_menu_name} option {digits} resolution failed: {e}")

            # Second priority: Fall back to legacy action/param if not resolved
            if not action and opt.ivr_menu_option_action:
                action = opt.ivr_menu_option_action
                param = opt.ivr_menu_option_param or ''

            logger.info(f"IVR {ivr.ivr_menu_name} option {digits} (type={dest_type}) resolved to: action={action}, param={param}")

            if action and param is not None:
                etree.SubElement(menu_el, 'entry', action=action, digits=digits, param=param)

        # ── Direct Dial (Extensions) ──────────────────────────────────────
        if ivr.ivr_menu_allow_internal_dial:
            # Caller types <digits># (mod_ivr terminates digit collection on #).
            # Route to the per-IVR fallback dialplan entry (ivr_dd_<short>) which
            # transfers to the extension if it exists, else runs the configured
            # invalid-extension fallback action.
            short = str(ivr.ivr_menu_uuid).replace('-', '')[:8]
            etree.SubElement(menu_el, 'entry', action='menu-exec-app',
                             digits='/^(\d{2,6})$/',
                             param=f'transfer ivr_dd_{short}$1 XML {ctx}')

    return etree.tostring(root, pretty_print=True, xml_declaration=True, encoding='UTF-8').decode()


def generate_xml_cdr_conf(domain_name=''):
    """Generate xml_cdr.conf so mod_xml_cdr knows the CDR POST URL."""
    callback_url = getattr(settings, 'FREESWITCH_CALLBACK_URL', 'http://localhost:8000')
    root = etree.Element('document', type='freeswitch/xml')
    section = etree.SubElement(root, 'section', name='configuration')
    conf = etree.SubElement(section, 'configuration', **{'name': 'xml_cdr.conf', 'description': 'XML CDR'})
    s = etree.SubElement(conf, 'settings')
    etree.SubElement(s, 'param', name='url', value=f'{callback_url}/xml-curl/cdr/')
    etree.SubElement(s, 'param', name='encode', value='true')
    etree.SubElement(s, 'param', name='retries', value='2')
    etree.SubElement(s, 'param', name='delay', value='5')
    etree.SubElement(s, 'param', name='log-dir', value='/tmp/cdr-failed')
    etree.SubElement(s, 'param', name='log-b-leg', value='true')
    return etree.tostring(root, pretty_print=True, xml_declaration=True, encoding='UTF-8').decode()


def generate_sofia_conf(domain_name=''):
    """Generate sofia.conf.xml from database SIP profiles."""
    from apps.sip_profiles.models import SipProfile, SipProfileSetting

    root = etree.Element('document', type='freeswitch/xml')
    section = etree.SubElement(root, 'section', name='configuration')
    conf = etree.SubElement(
        section,
        'configuration',
        **{'name': 'sofia.conf', 'description': 'Sofia SIP'},
    )

    profiles_el = etree.SubElement(conf, 'profiles')

    from apps.gateways.models import Gateway

    for profile in SipProfile.objects.filter(sip_profile_enabled=True):
        p_el = etree.SubElement(profiles_el, 'profile', name=profile.sip_profile_name)
        settings_el = etree.SubElement(p_el, 'settings')
        for s in profile.settings.filter(sip_profile_setting_enabled=True):
            etree.SubElement(
                settings_el,
                'param',
                name=s.sip_profile_setting_name,
                value=s.sip_profile_setting_value or '',
            )

        # Gateways (VoIP trunks) belonging to this SIP profile
        gateways_el = etree.SubElement(p_el, 'gateways')
        for gw in Gateway.objects.filter(profile=profile.sip_profile_name, gateway_enabled=True):
            gw_el = etree.SubElement(gateways_el, 'gateway', name=gw.gateway)

            trunk_type = getattr(gw, 'trunk_type', 'register') or 'register'

            # ── Credentials (not emitted for peer/IP trunks) ─────────────
            if trunk_type in ('register', 'account'):
                for param_name, value in [
                    ('username',       gw.username),
                    ('password',       gw.password),
                    ('auth-username',  gw.auth_username),
                    ('realm',          gw.realm),
                ]:
                    if value:
                        etree.SubElement(gw_el, 'param', name=param_name, value=value)

            # ── Routing / SIP address ────────────────────────────────────
            for param_name, value in [
                ('proxy',          gw.proxy),
                ('register-proxy', gw.register_proxy),
                ('outbound-proxy', gw.outbound_proxy),
                ('from-user',      gw.from_user),
                ('from-domain',    gw.from_domain),
            ]:
                if value:
                    etree.SubElement(gw_el, 'param', name=param_name, value=value)

            # ── Register param (driven by trunk_type) ────────────────────
            # register  → always true
            # account   → always false (digest on outbound, no REGISTER)
            # peer      → always false (IP-based, no auth)
            do_register = (trunk_type == 'register')
            etree.SubElement(gw_el, 'param', name='register',
                             value='true' if do_register else 'false')

            if do_register:
                etree.SubElement(gw_el, 'param', name='register-transport',
                                 value=gw.register_transport or 'udp')
                if gw.expire_seconds:
                    etree.SubElement(gw_el, 'param', name='expire-seconds',
                                     value=str(gw.expire_seconds))
                if gw.retry_seconds:
                    etree.SubElement(gw_el, 'param', name='retry-seconds',
                                     value=str(gw.retry_seconds))

            # ── Codec / misc ─────────────────────────────────────────────
            if gw.codec_prefs:
                etree.SubElement(gw_el, 'param', name='codec-prefs', value=gw.codec_prefs)
            if gw.ping:
                etree.SubElement(gw_el, 'param', name='ping', value=gw.ping)
            if gw.extension and gw.extension != 'auto_to_user':
                etree.SubElement(gw_el, 'param', name='extension', value=gw.extension)
            if gw.caller_id_in_from:
                etree.SubElement(gw_el, 'param', name='caller-id-in-from', value='true')

    return etree.tostring(root, pretty_print=True, xml_declaration=True, encoding='UTF-8').decode()


def generate_voicemail_conf(domain_name=''):
    """Generate voicemail.conf.xml with PostgreSQL storage.

    Greeting behaviour:
      - Plays "please leave your message after the beep, hang up when done"
      - No "press any key to leave a message" prompt (ack-all=false)
      - Max recording length taken from the tenant's voicemail_timeout setting
    """
    from django.conf import settings
    db = settings.DATABASES['default']
    host = db.get('HOST', 'localhost') or 'localhost'
    port = db.get('PORT', '5432') or '5432'
    name = db.get('NAME', 'fusionpbx')
    user = db.get('USER', 'fusionpbx')
    password = db.get('PASSWORD', '')
    dsn = (
        f"pgsql://hostaddr={host} port={port} dbname={name} "
        f"user={user} password={password} "
        f"options='-c client_min_messages=NOTICE' application_name=freeswitch"
    )

    # Determine max recording length from tenant settings
    # Use the shortest non-zero tenant timeout, or fall back to 120 s
    max_len = 120
    try:
        from core.models import Tenant
        timeouts = list(
            Tenant.objects.filter(tenant_enabled=True, voicemail_timeout__gt=0)
            .values_list('voicemail_timeout', flat=True)
        )
        if timeouts:
            max_len = max(timeouts)  # use the largest; per-mailbox vm-max-recording-len overrides this
    except Exception:
        pass

    root = etree.Element('document', type='freeswitch/xml')
    section = etree.SubElement(root, 'section', name='configuration')
    conf = etree.SubElement(
        section,
        'configuration',
        **{'name': 'voicemail.conf', 'description': 'Voicemail'},
    )
    profiles_el = etree.SubElement(conf, 'profiles')
    profile_el = etree.SubElement(profiles_el, 'profile', name='default')
    params_el = etree.SubElement(profile_el, 'params')
    etree.SubElement(params_el, 'param', name='odbc-dsn', value=dsn)
    etree.SubElement(params_el, 'param', name='file-extension', value='wav')
    etree.SubElement(params_el, 'param', name='db-name', value='voicemail_msgs')
    etree.SubElement(params_el, 'param', name='odbc-dbname', value='voicemail_msgs')
    # Disable "press any key to leave a message" — caller hears beep and records immediately
    etree.SubElement(params_el, 'param', name='ack-all', value='false')
    # After the beep instruction phrase (uses FreeSWITCH built-in phrase)
    etree.SubElement(params_el, 'param', name='auto-playback-recordings', value='true')
    etree.SubElement(params_el, 'param', name='max-record-len', value=str(max_len))
    return etree.tostring(root, pretty_print=True, xml_declaration=True, encoding='UTF-8').decode()


def generate_callcenter_conf(domain_name=''):
    """Generate callcenter.conf.xml from database queues."""
    from apps.call_centers.models import CallCenter, CallCenterAgent, CallCenterTier

    root = etree.Element('document', type='freeswitch/xml')
    section = etree.SubElement(root, 'section', name='configuration')
    conf = etree.SubElement(
        section,
        'configuration',
        **{'name': 'callcenter.conf', 'description': 'Call Center'},
    )

    etree.SubElement(conf, 'settings')

    queues_el = etree.SubElement(conf, 'queues')
    for queue in CallCenter.objects.filter(enabled=True):
        q_el = etree.SubElement(queues_el, 'queue', name=queue.queue_name)
        for field, value in [
            ('strategy', queue.strategy),
            ('moh-sound', queue.moh_sound or ''),
            ('time-base-score', queue.time_base_score or 'queue'),
            ('max-wait-time', str(queue.max_wait_time or 0)),
            ('max-wait-time-with-no-agent', str(queue.max_wait_time_with_no_agent or 0)),
            ('timeout-action', queue.timeout_action or ''),
        ]:
            etree.SubElement(q_el, 'param', name=field, value=str(value) if value else '')

    agents_el = etree.SubElement(conf, 'agents')
    for agent in CallCenterAgent.objects.filter(enabled=True):
        a_el = etree.SubElement(agents_el, 'agent', name=agent.agent_name)
        etree.SubElement(a_el, 'param', name='type', value=agent.agent_type or 'callback')
        etree.SubElement(a_el, 'param', name='contact', value=agent.agent_contact or '')
        etree.SubElement(a_el, 'param', name='wrap-up-time', value=str(agent.wrap_up_time or 0))
        etree.SubElement(a_el, 'param', name='max-no-answer', value=str(agent.max_no_answer or 0))

    tiers_el = etree.SubElement(conf, 'tiers')
    for tier in CallCenterTier.objects.all():
        t_el = etree.SubElement(tiers_el, 'tier')
        etree.SubElement(t_el, 'param', name='agent', value=tier.tier_agent or '')
        etree.SubElement(
            t_el,
            'param',
            name='queue',
            value=tier.call_center.queue_name if tier.call_center else '',
        )
        etree.SubElement(t_el, 'param', name='level', value=str(tier.tier_level or 1))
        etree.SubElement(t_el, 'param', name='position', value=str(tier.tier_position or 1))

    return etree.tostring(root, pretty_print=True, xml_declaration=True, encoding='UTF-8').decode()


def generate_conference_conf(domain_name=''):
    """Generate conference.conf.xml from database conference profiles."""
    from apps.conferences.models import ConferenceProfile, ConferenceProfileSetting

    root = etree.Element('document', type='freeswitch/xml')
    section = etree.SubElement(root, 'section', name='configuration')
    conf = etree.SubElement(
        section,
        'configuration',
        **{'name': 'conference.conf', 'description': 'Conference'},
    )
    profiles_el = etree.SubElement(conf, 'profiles')

    for profile in ConferenceProfile.objects.filter(enabled=True):
        p_el = etree.SubElement(profiles_el, 'profile', name=profile.conference_profile_name)
        for s in profile.settings.filter(enabled=True):
            etree.SubElement(
                p_el,
                'param',
                name=s.conference_profile_setting_name,
                value=s.conference_profile_setting_value or '',
            )

    return etree.tostring(root, pretty_print=True, xml_declaration=True, encoding='UTF-8').decode()


def generate_acl_conf(domain_name=''):
    """Generate acl.conf.xml from access controls."""
    from apps.access_controls.models import AccessControl, AccessControlNode

    root = etree.Element('document', type='freeswitch/xml')
    section = etree.SubElement(root, 'section', name='configuration')
    conf = etree.SubElement(
        section,
        'configuration',
        **{'name': 'acl.conf', 'description': 'ACL'},
    )
    network_lists = etree.SubElement(conf, 'network-lists')

    for acl in AccessControl.objects.filter(enabled=True):
        list_el = etree.SubElement(
            network_lists,
            'list',
            name=acl.access_control_name,
            default=acl.default_action or 'deny',
        )
        for node in acl.nodes.filter(enabled=True):
            etree.SubElement(
                list_el,
                'node',
                type=node.node_type or 'allow',
                cidr=node.node_cidr or '',
            )

    return etree.tostring(root, pretty_print=True, xml_declaration=True, encoding='UTF-8').decode()
