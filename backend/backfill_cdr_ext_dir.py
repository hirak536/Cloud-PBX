"""One-off backfill for CDR extension_number (A-legs) and direction.

Run: venv/bin/python manage.py shell -c "exec(open('backfill_cdr_ext_dir.py').read())"
Set DRY=False to apply.
"""
from apps.xml_cdr.models import XmlCdr
from django.db.models import Q

DRY = globals().get('DRY', True)


def looks_internal(v):
    if not v:
        return False
    head = str(v).split('-', 1)[0]
    return head.isdigit() and 1 <= len(head) <= 6


# ---- 1. extension backfill: B-leg ext -> blank A-leg (matched by uuid) ----
# Iterate only over B-legs that carry an internal extension (small set).
b_legs = (XmlCdr.objects.filter(leg='b')
          .exclude(extension_number='').exclude(extension_number__isnull=True)
          .values('call_uuid', 'bridge_uuid', 'extension_number'))
ext_fixed = 0
seen = set()
for b in b_legs.iterator(chunk_size=2000):
    ext = b['extension_number']
    if not looks_internal(ext):
        continue
    uuids = [str(u) for u in (b['bridge_uuid'], b['call_uuid']) if u]
    key = (tuple(uuids), ext)
    if key in seen:
        continue
    seen.add(key)
    qs = XmlCdr.objects.filter(leg='a', call_uuid__in=uuids).filter(
        Q(extension_number='') | Q(extension_number__isnull=True))
    if DRY:
        ext_fixed += qs.count()
    else:
        ext_fixed += qs.update(extension_number=ext)
print(f"[ext] A-legs {'would be' if DRY else ''} updated: {ext_fixed}")

# ---- 2. direction: authenticated context = outbound ----
auth_qs = XmlCdr.objects.filter(context='authenticated', direction='inbound')
n_auth = auth_qs.count()
if not DRY:
    auth_qs.update(direction='outbound')
print(f"[dir] authenticated->outbound: {n_auth}")

# ---- 3. direction: empty-context outbound (internal caller -> PSTN dest) ----
# Conservative: short numeric caller_id, long numeric destination, currently inbound.
empty_qs = XmlCdr.objects.filter(context='', direction='inbound').exclude(
    hangup_cause='NO_ROUTE_DESTINATION')
n_empty = 0
ids = []
for c in empty_qs.values('xml_cdr_uuid', 'caller_id_number', 'destination_number').iterator(chunk_size=2000):
    cd = (c['caller_id_number'] or '').lstrip('+')
    dd = (c['destination_number'] or '').lstrip('+')
    if cd.isdigit() and len(cd) <= 6 and dd.isdigit() and len(dd) >= 7:
        ids.append(c['xml_cdr_uuid'])
n_empty = len(ids)
if not DRY and ids:
    for i in range(0, len(ids), 1000):
        XmlCdr.objects.filter(xml_cdr_uuid__in=ids[i:i+1000]).update(direction='outbound')
print(f"[dir] empty-ctx internal->PSTN ->outbound: {n_empty}")
print("DRY RUN — no changes written" if DRY else "APPLIED")
