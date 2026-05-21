#!/usr/bin/env python3
"""
check_outbound_raw.py — dump raw outbound XmlCdr rows for a tenant to figure out
where the actual dialing extension is hiding (since 'realsrc' collapsed to 417
across hundreds of agents in the affinity preview).

Usage:
    python check_outbound_raw.py --tenant GMD [--did 2812470858] [--customer 8328770806] [--limit 30]
"""
import os, sys, argparse, django
from collections import Counter

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.dev')
django.setup()

from core.models import Tenant
from apps.xml_cdr.models import XmlCdr


def run(tenant_code, did, customer, limit):
    tenant = Tenant.objects.get(tenant_code=tenant_code)
    qs = (XmlCdr.objects
          .filter(tenant=tenant, direction='outbound')
          .exclude(extension_number=''))
    if did:
        qs = qs.filter(caller_id_number__contains=did[-10:])
    if customer:
        qs = qs.filter(destination_number__contains=customer[-10:])
    qs = qs.order_by('-start_stamp')

    total = qs.count()
    print(f"Tenant: {tenant_code}  outbound rows matching filter: {total}\n")

    # First: distribution of extension_number for these outbound rows
    ext_counts = Counter(qs.values_list('extension_number', flat=True)[:5000])
    print("extension_number distribution (first 5000 outbound rows in filter):")
    for ext, n in ext_counts.most_common(20):
        print(f"  {ext or '(blank)':10s} {n}")
    print()

    print(f"--- raw sample (newest {limit}) ---")
    fields = ['start_stamp', 'caller_id_number', 'caller_id_name', 'destination_number',
              'extension_number', 'caller_destination', 'context', 'last_app', 'last_arg',
              'billsec', 'hangup_cause']
    for row in qs.values(*fields)[:limit]:
        print()
        for f in fields:
            v = row[f]
            if hasattr(v, 'strftime'):
                v = v.strftime('%Y-%m-%d %H:%M:%S')
            print(f"  {f:22s}  {v}")


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--tenant', required=True)
    p.add_argument('--did', default='')
    p.add_argument('--customer', default='')
    p.add_argument('--limit', type=int, default=20)
    args = p.parse_args()
    run(args.tenant, args.did, args.customer, args.limit)
