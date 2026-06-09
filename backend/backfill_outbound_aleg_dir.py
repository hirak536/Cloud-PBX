"""Backfill: flip mislabeled outbound A-legs from 'inbound' -> 'outbound'.

These are calls placed FROM an extension OUT to the PSTN. The gateway B-leg was
correctly recorded as outbound, but the originating A-leg (the row shown in the
CDR list) was left as 'inbound' because ihs_direction was only export'ed, not
set locally on the A-leg. Fixed at source in freeswitch_config/generators.py;
this repairs the historical rows.

Criteria (conservative): A-leg currently direction='inbound', whose paired call
(B-leg, matched by uuid) bridged to a sofia gateway. That gateway-bridge signature
is what makes it a true PSTN-bound outbound call, not an internal ext-to-ext leg.

We do NOT backfill extension_number: the originating extension was sip_from_user,
which is not stored on the A-leg CDR, and the B-leg's extension_number on a
gateway leg is the PSTN caller-ID, not the dialing extension. So flipping
direction is the safe, correct repair; extension stays as-is.

Run: venv/bin/python manage.py shell -c "exec(open('backfill_outbound_aleg_dir.py').read())"
Set DRY=False to apply.
"""
from apps.xml_cdr.models import XmlCdr

DRY = globals().get('DRY', True)

# Paired-call uuids whose B-leg bridged to a gateway = true outbound PSTN call.
gw_b = (XmlCdr.objects.filter(leg='b', direction='outbound', last_app__iexact='bridge',
                              last_arg__icontains='sofia/gateway/')
        .values_list('bridge_uuid', flat=True))  # B-leg's bridge_uuid == A-leg's call_uuid
a_call_uuids = {u for u in gw_b.iterator(chunk_size=2000) if u}

cand = XmlCdr.objects.filter(leg='a', direction='inbound', call_uuid__in=list(a_call_uuids))
n = cand.count()
print(f"A-legs to flip inbound->outbound (gateway-bridged calls): {n}")
if not DRY:
    updated = 0
    ids = list(cand.values_list('xml_cdr_uuid', flat=True))
    for i in range(0, len(ids), 1000):
        updated += XmlCdr.objects.filter(xml_cdr_uuid__in=ids[i:i+1000]).update(direction='outbound')
    print(f"APPLIED: {updated} rows set to outbound")
else:
    print("DRY RUN — no changes written (set DRY=False to apply)")
