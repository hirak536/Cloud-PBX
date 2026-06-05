"""
Shared helper for determining which extensions route no-answer calls to voicemail.

A missed/no-answer call to such an extension is reported as "went to voicemail"
across every CDR API (client API + admin panel), even when FreeSWITCH did not log
a separate voicemail leg. This mirrors the dialplan rule in
freeswitch_config.generators._extension_to_dialplan_xml: voicemail is enabled AND
the call is not forwarded elsewhere on no-answer (or the no-answer forward target
is itself voicemail).

The returned set contains BOTH the plain extension number ("906") and the SIP
username ("906-IHDT"), because XmlCdr.extension_number may hold either form.
"""


def vm_route_idents(tenant=None):
    """Return the set of extension identifiers whose no-answer routing is voicemail.

    Pass a tenant to scope the lookup (recommended); omit it to scan all extensions
    (used by the admin panel, which is not tenant-scoped).
    """
    from apps.extensions.models import Extension

    qs = Extension.objects.all()
    if tenant is not None:
        qs = qs.filter(tenant=tenant)

    idents = set()
    for ext_ext, ext_sip, vm_en, fwd_en, fwd_dest in qs.values_list(
        'extension', 'sip_username',
        'voicemail_enabled', 'forward_no_answer_enabled', 'forward_no_answer_destination',
    ):
        routes_to_vm = vm_en and (
            not fwd_en or 'voicemail' in (fwd_dest or '').lower()
        )
        if routes_to_vm:
            for ident in (ext_ext, ext_sip):
                if ident:
                    idents.add(ident)
    return idents
