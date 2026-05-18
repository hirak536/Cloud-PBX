"""
Debug script: show the generated dialplan XML for a ring group.

Run on server:
  cd /opt/ihspbx-django && python backend/manage.py shell < debug_ringgroup.py
"""

TENANT_CODE = 'IHS'
DID_NUMBER  = '+12293025400'

import re
from django.db import models as dm

print(f"\n{'='*60}")
print(f"RING GROUP DEBUG: DID {DID_NUMBER} → ring group")
print(f"{'='*60}\n")

from core.models import Domain, Tenant
from apps.destinations.models import Destination

domain = Domain.objects.filter(domain_enabled=True).first()
tenant = Tenant.objects.filter(tenant_code=TENANT_CODE).first()
print(f"Domain: {domain}  Tenant: {tenant}\n")

# ── 1. What is the DID routed to? ────────────────────────────────
print(f"[All DIDs in domain]")
for d in Destination.objects.filter(domain=domain).order_by('destination_number'):
    print(f"  {d.destination_number!r}  type={d.dest_type}  enabled={d.destination_enabled}  target={d.dest_target_uuid}")
print()

try:
    did = Destination.objects.get(destination_number=DID_NUMBER, domain=domain)
except Destination.DoesNotExist:
    # try without domain filter (maybe domain mismatch)
    did = Destination.objects.filter(destination_number=DID_NUMBER).first()
    if did:
        print(f"WARNING: DID found but on domain={did.domain}, not {domain}")
    else:
        print(f"DID {DID_NUMBER} not found in any domain!")
        import sys; sys.exit()

print(f"[DID {DID_NUMBER}]")
print(f"  dest_type          : {did.dest_type}")
print(f"  dest_target_uuid   : {did.dest_target_uuid}")
print(f"  destination_enabled: {did.destination_enabled}")

print()

# ── 2. Ring group details ─────────────────────────────────────────
from apps.ring_groups.models import RingGroup

rg = None
if did.dest_type == 'ring_group' and did.dest_target_uuid:
    try:
        rg = RingGroup.objects.prefetch_related('destinations').get(
            ring_group_uuid=did.dest_target_uuid
        )
    except RingGroup.DoesNotExist:
        print(f"Ring group UUID {did.dest_target_uuid} NOT FOUND!")
        exit()

if not rg:
    print(f"DID is not routed to a ring group (dest_type={did.dest_type})")
    exit()

print(f"[Ring Group: {rg.ring_group_name}]")
print(f"  extension  : {rg.ring_group_extension}")
print(f"  strategy   : {rg.ring_group_strategy}")
print(f"  timeout    : {rg.ring_group_call_timeout}")
print(f"  tenant     : {rg.tenant}")
print()

destinations = list(rg.destinations.all())
print(f"  Destinations ({len(destinations)}):")
for d in destinations:
    print(f"    number={d.destination_number!r}  delay={d.destination_delay}  timeout={d.destination_timeout}")
print()

# ── 3. Simulate bridge string generation ─────────────────────────
call_timeout = rg.ring_group_call_timeout or 60
tenant_code = rg.tenant.tenant_code if rg.tenant else None
domain_name = str(domain)
strategy = rg.ring_group_strategy

print(f"[Generated bridge string]  tenant_code={tenant_code!r}")
legs = []
for dest in destinations:
    number = dest.destination_number
    dest_timeout = dest.destination_timeout or call_timeout
    if re.match(r'^\d{3,6}$', number):
        sip_user = f'{number}-{tenant_code}' if tenant_code else number
        leg = f'[call_timeout={dest_timeout}]user/{sip_user}@{domain_name}'
    else:
        from freeswitch_config.generators import _get_default_gateway
        gw = _get_default_gateway(domain_name)
        leg = f'[call_timeout={dest_timeout}]sofia/gateway/{gw}/{number}'
    print(f"  leg: {leg}")
    legs.append(leg)

if strategy == 'simultaneous':
    bridge_str = ':'.join(legs)
else:
    bridge_str = ','.join(legs)

print(f"\n  Final bridge: {bridge_str}")

# ── 4. Are both SIP users registered? ────────────────────────────
print(f"\n[SIP registration check]")
try:
    from esl.client import ESLClient
    with ESLClient() as esl:
        for dest in destinations:
            number = dest.destination_number
            if re.match(r'^\d{3,6}$', number):
                sip_user = f'{number}-{tenant_code}' if tenant_code else number
                result = esl.send(f'api sofia_contact */{sip_user}@{domain_name}')
                print(f"  sofia_contact {sip_user}@{domain_name} → {result.strip()}")
except Exception as e:
    print(f"  (ESL check failed: {e})")
    print(f"  Run manually on server:")
    for dest in destinations:
        number = dest.destination_number
        if re.match(r'^\d{3,6}$', number):
            sip_user = f'{number}-{tenant_code}' if tenant_code else number
            print(f"    fs_cli -x 'sofia_contact */{sip_user}@{domain_name}'")

print(f"\n{'='*60}\n")
