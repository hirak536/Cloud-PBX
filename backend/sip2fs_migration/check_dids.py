import os, django
os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings.dev'
django.setup()
from apps.destinations.models import Destination
from core.models import Tenant, Domain

t = Tenant.objects.get(tenant_code='GMD')

# Resolve domain
domain = (
    t.domains.filter(domain_enabled=True).first()
    or Domain.objects.filter(domain_universal=True, domain_enabled=True).first()
    or Domain.objects.filter(domain_enabled=True).first()
)
print(f"Domain: {domain}")

# Patch existing DIDs with no domain
patched = Destination.objects.filter(tenant=t, domain__isnull=True).update(domain=domain)
print(f"Patched {patched} DIDs with domain")

dids = Destination.objects.filter(tenant=t)
print(f"DIDs for GMD: {dids.count()}")
for d in dids:
    print(f"  {d.destination_number} | {d.destination_name} | domain={d.domain_id}")
