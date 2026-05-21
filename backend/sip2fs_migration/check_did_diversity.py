#!/usr/bin/env python3
"""
check_did_diversity.py — classify each DID by how diverse its outbound agent
extensions are. DIDs where a single extension dominates outbound calls are
likely shared/queue lines and should be excluded from affinity seeding.

Usage:
    python check_did_diversity.py --tenant GMD [--min-calls 5]
"""
import os, sys, argparse, django
from collections import defaultdict, Counter

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.dev')
django.setup()

from core.models import Tenant
from apps.xml_cdr.models import XmlCdr


def run(tenant_code, min_calls):
    tenant = Tenant.objects.get(tenant_code=tenant_code)

    # Per-DID extension distribution for outbound calls
    by_did = defaultdict(Counter)
    qs = (XmlCdr.objects
          .filter(tenant=tenant, direction='outbound')
          .exclude(extension_number='')
          .exclude(caller_id_number='')
          .values_list('caller_id_number', 'extension_number'))

    for did, ext in qs.iterator(chunk_size=5000):
        # Normalize DID — strip non-digits, last 10
        digits = ''.join(c for c in did if c.isdigit())
        if len(digits) > 10 and digits.startswith('1'):
            digits = digits[1:]
        did_n = digits[-10:] if len(digits) >= 10 else digits
        if did_n:
            by_did[did_n][ext] += 1

    rows = []
    for did, ext_counter in by_did.items():
        total = sum(ext_counter.values())
        if total < min_calls:
            continue
        distinct = len(ext_counter)
        dom_ext, dom_count = ext_counter.most_common(1)[0]
        dom_share = dom_count / total
        looks_shared = distinct < 3 or dom_share > 0.80
        rows.append({
            'did': did,
            'total': total,
            'distinct_ext': distinct,
            'dom_ext': dom_ext,
            'dom_share': dom_share,
            'looks_shared': looks_shared,
        })

    rows.sort(key=lambda r: r['total'], reverse=True)

    shared = [r for r in rows if r['looks_shared']]
    normal = [r for r in rows if not r['looks_shared']]

    print(f"Tenant: {tenant_code}  DIDs with >= {min_calls} outbound calls: {len(rows)}")
    print(f"  shared-looking DIDs (exclude from affinity seeding): {len(shared)}")
    print(f"  normal DIDs (seed from outbound):                    {len(normal)}\n")

    print(f"{'DID':12s}  {'calls':>6s}  {'distinct':>8s}  {'dom_ext':>7s}  {'dom_share':>9s}  shared?")
    print('-' * 70)
    for r in rows:
        flag = '*** SHARED ***' if r['looks_shared'] else ''
        print(f"{r['did']:12s}  {r['total']:>6d}  {r['distinct_ext']:>8d}  {r['dom_ext']:>7s}  {r['dom_share']:>9.0%}  {flag}")


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--tenant', required=True)
    p.add_argument('--min-calls', type=int, default=5, help='Ignore DIDs with fewer than N outbound calls')
    args = p.parse_args()
    run(args.tenant, args.min_calls)
