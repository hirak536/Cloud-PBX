import os, django
os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings.dev'
django.setup()
from core.models import Tenant, Domain

t = Tenant.objects.get(tenant_code='GMD')
print(f"Tenant: {t}")
print(f"Domains linked to tenant: {list(t.domains.values('domain_uuid', 'domain_name', 'domain_enabled'))}")
print()
print("All enabled domains:")
for d in Domain.objects.filter(domain_enabled=True):
    print(f"  {d.domain_name} | universal={d.domain_universal} | tenant={d.tenant_id}")
