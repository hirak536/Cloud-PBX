"""
Debug script: why did a call to +18322715337 ring extension 902?

Run on server:
  cd /opt/ihspbx-django
  python backend/manage.py shell < debug_call_routing.py

Or via SSH one-liner:
  ssh user@server "cd /opt/ihspbx-django && python backend/manage.py shell < debug_call_routing.py"
"""
import os, re, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

TENANT_CODE = 'IHS'
EXT_901     = '901'
EXT_902     = '902'
DIALED      = '+18322715337'

print(f"\n{'='*60}")
print(f"CALL ROUTING DEBUG: {EXT_901} → {DIALED}")
print(f"{'='*60}\n")

# ── 1. Extension 901 config ───────────────────────────────────────
from apps.extensions.models import Extension
from core.models import Tenant

tenant = Tenant.objects.filter(tenant_code=TENANT_CODE).first()
print(f"Tenant: {tenant}\n")

try:
    ext901 = Extension.objects.select_related('tenant', 'outbound_route').get(
        extension=EXT_901, tenant=tenant
    )
    print(f"[Extension {EXT_901}]")
    print(f"  sip_username          : {ext901.sip_username}")
    print(f"  call_forward_active   : {ext901.call_forward_active}")
    print(f"  forward_all_enabled   : {ext901.forward_all_enabled}  → {ext901.forward_all_destination}")
    print(f"  forward_busy_enabled  : {ext901.forward_busy_enabled}  → {ext901.forward_busy_destination}")
    print(f"  forward_no_ans_enabled: {ext901.forward_no_answer_enabled}  → {ext901.forward_no_answer_destination}")
    print(f"  forward_unreg_enabled : {ext901.forward_user_not_registered_enabled}  → {ext901.forward_user_not_registered_destination}")
    print(f"  forward_cond_enabled  : {ext901.forward_on_condition_enabled}  → {ext901.forward_on_condition_destination}")
    print(f"  outbound_route        : {ext901.outbound_route}")
    print(f"  number_alias          : {ext901.number_alias}")
except Extension.DoesNotExist:
    print(f"  Extension {EXT_901} NOT FOUND for tenant {TENANT_CODE}")

print()

# ── 2. Extension 902 config ───────────────────────────────────────
try:
    ext902 = Extension.objects.select_related('tenant').get(
        extension=EXT_902, tenant=tenant
    )
    print(f"[Extension {EXT_902}]")
    print(f"  sip_username          : {ext902.sip_username}")
    print(f"  number_alias          : {ext902.number_alias}")
    print(f"  voicemail_id          : {ext902.voicemail_id}")
    print(f"  voicemail_enabled     : {ext902.voicemail_enabled}")
    print(f"  call_forward_active   : {ext902.call_forward_active}")
    print(f"  forward_all_enabled   : {ext902.forward_all_enabled}  → {ext902.forward_all_destination}")
except Extension.DoesNotExist:
    print(f"  Extension {EXT_902} NOT FOUND for tenant {TENANT_CODE}")

print()

# ── 3. Outbound routes for this tenant ───────────────────────────
from apps.outbound_routes.models import OutboundRoute
from django.db import models as dm
from core.models import Domain

domain = Domain.objects.filter(domain_enabled=True).first()
routes = OutboundRoute.objects.filter(
    outbound_route_enabled=True,
).filter(
    dm.Q(domain=domain) | dm.Q(domain__isnull=True)
).select_related('tenant', 'gateway', 'gateway_2', 'gateway_3').order_by(
    'outbound_route_order', 'outbound_route_name'
)

print(f"[Outbound Routes for domain={domain}]")
for r in routes:
    match = re.search(r.dialplan_pattern, DIALED)
    captured = match.group(1) if match and match.lastindex else (match.group(0) if match else None)
    prepend  = r.prepend or ''
    would_dial = f"{prepend}{captured}" if captured else '(no match)'
    print(f"  [{r.outbound_route_name}]  tenant={r.tenant}  pattern={r.dialplan_pattern!r}")
    print(f"    prepend={prepend!r}  gateway={r.gateway}")
    print(f"    Match against {DIALED!r}: captured={captured!r}  would_dial={would_dial!r}")
    print()

# ── 4. Does any extension have 18322715337 as number_alias or forward dest? ─
print(f"[Extensions with number_alias or forward matching {DIALED}]")
hits = Extension.objects.filter(
    dm.Q(number_alias__icontains='8322715337') |
    dm.Q(forward_all_destination__icontains='8322715337') |
    dm.Q(forward_busy_destination__icontains='8322715337') |
    dm.Q(forward_no_answer_destination__icontains='8322715337') |
    dm.Q(forward_user_not_registered_destination__icontains='8322715337') |
    dm.Q(forward_on_condition_destination__icontains='8322715337')
).select_related('tenant')
if hits:
    for h in hits:
        print(f"  ext={h.extension}  tenant={h.tenant}  number_alias={h.number_alias!r}")
        print(f"    forward_all={h.forward_all_destination!r}  forward_busy={h.forward_busy_destination!r}")
        print(f"    forward_no_ans={h.forward_no_answer_destination!r}")
else:
    print("  (none)")

print()

# ── 5. Ring groups containing 901 or 902 ─────────────────────────
try:
    from apps.ring_groups.models import RingGroup, RingGroupDestination
    rg_with_901 = RingGroup.objects.filter(
        destinations__destination_number__in=[EXT_901, f'{EXT_901}-{TENANT_CODE}'],
        tenant=tenant,
    ).distinct()
    print(f"[Ring groups containing ext {EXT_901}]")
    for rg in rg_with_901:
        timeout_type = rg.ring_group_timeout_type
        timeout_target = rg.ring_group_timeout_target_uuid
        print(f"  RG: {rg.ring_group_name}  ext={rg.ring_group_extension}")
        print(f"    timeout_type={timeout_type}  timeout_target={timeout_target}")
        print(f"    destinations: {list(rg.destinations.values_list('destination_number', flat=True))}")
    if not rg_with_901:
        print("  (none)")
except Exception as e:
    print(f"  (ring groups query failed: {e})")

print()

# ── 6. Recent CDR for this call ───────────────────────────────────
try:
    from freeswitch_config.models import XmlCdr
    from django.utils.timezone import now
    from datetime import timedelta
    recent = XmlCdr.objects.filter(
        domain=domain,
        start_epoch__gte=(now() - timedelta(hours=2)),
    ).filter(
        dm.Q(caller_id_number__icontains='901') | dm.Q(destination_number__icontains='8322715337')
    ).order_by('-start_epoch')[:10]
    print(f"[Recent CDRs (last 2h) matching 901 or {DIALED}]")
    for c in recent:
        print(f"  {c.start_epoch}  {c.caller_id_number} → {c.destination_number}"
              f"  dir={c.direction}  last_app={c.last_app}  last_arg={c.last_arg!r}"
              f"  hangup={c.hangup_cause}")
    if not recent:
        print("  (none)")
except Exception as e:
    print(f"  (CDR query failed: {e})")

print(f"\n{'='*60}\n")
