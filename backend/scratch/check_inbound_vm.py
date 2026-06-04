"""
Diagnose: incoming.voicemail=1 but voicemail.total=0

Run on the box:
    cd /opt/IHS-PBX/backend
    python manage.py shell < scratch/check_inbound_vm.py

Optionally set TENANT_CODE / START / END below to match the dashboard filter
that produced the 1-vs-0 numbers.
"""
from django.db.models import Q
from apps.xml_cdr.models import XmlCdr
from apps.voicemails.models import VoicemailMessage
from core.models import Tenant

# ── Adjust to match the dashboard query that showed 1 vs 0 ──────────────
TENANT_CODE = None        # e.g. 'IHS' — leave None to scan all tenants
START = None              # e.g. '2026-06-01'  (ISO) — leave None for no lower bound
END = None                # e.g. '2026-06-04'
# ────────────────────────────────────────────────────────────────────────

# Same _VOICEMAIL_Q used by the stats endpoint (client_api/views.py:408)
_VOICEMAIL_Q = (
    Q(last_app='voicemail') |
    Q(last_app='speak', last_arg__contains='|') |
    Q(last_app='record', last_arg__contains='/voicemail/') |
    Q(last_app='system', last_arg__contains='voicemail-messages/ingest') |
    Q(last_app='phrase', last_arg__contains='voicemail')
)

qs = XmlCdr.objects.filter(Q(direction='inbound') & _VOICEMAIL_Q)
if TENANT_CODE:
    qs = qs.filter(tenant__tenant_code=TENANT_CODE)
if START:
    qs = qs.filter(start_stamp__gte=START)
if END:
    qs = qs.filter(start_stamp__lte=END)

print(f"\n=== Inbound CDR legs counted as voicemail: {qs.count()} ===\n")
for c in qs.order_by('-start_stamp'):
    print(f"  start={c.start_stamp}  caller={c.caller_id_number!r}  dest={c.destination_number!r}")
    print(f"    last_app={c.last_app!r}  last_arg={c.last_arg!r}")
    print(f"    hangup_cause={c.hangup_cause!r}  billsec={c.billsec}  duration={c.duration}  missed={c.missed_call}")
    print(f"    domain={c.domain.domain_name if c.domain_id else None!r}  record_path={c.record_path!r}")
    print()

# ── Now check what VoicemailMessage rows actually exist ─────────────────
print("=== VoicemailMessage rows (any folder) ===")
vm_all = VoicemailMessage.objects.all()
if TENANT_CODE:
    t = Tenant.objects.filter(tenant_code=TENANT_CODE).first()
    if t:
        domain_names = list(t.domains.values_list('domain_name', flat=True))
        print(f"  tenant domains: {domain_names}")
print(f"  total rows (all): {vm_all.count()}")
print(f"  in_folder='inbox': {vm_all.filter(in_folder='inbox').count()}")
print("  by (domain, in_folder, created_epoch):")
for vm in vm_all.order_by('-created_epoch')[:20]:
    print(f"    domain={vm.domain!r}  username={vm.username!r}  folder={vm.in_folder!r}  "
          f"created_epoch={vm.created_epoch!r}  read_flags={vm.read_flags!r}")
