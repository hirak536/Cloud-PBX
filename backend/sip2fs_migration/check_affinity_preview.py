#!/usr/bin/env python3
"""
check_affinity_preview.py — dry-run preview of the caller→extension affinity seeder.

Reads existing XmlCdr rows for a tenant and prints what the affinity table WOULD
contain if we ran the real seeder. Writes nothing. Use this to validate the rule
set against real data before committing to a model.

Usage (run from backend/):
    python check_affinity_preview.py --tenant GMD [--limit 50] [--did 2812470858]
"""

import os
import re
import sys
import argparse
import django
from collections import defaultdict

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.dev')
django.setup()

from core.models import Tenant
from apps.xml_cdr.models import XmlCdr


def normalize_number(num):
    """Strip non-digits, drop leading country code, keep last 10 digits for US numbers."""
    if not num:
        return ''
    digits = re.sub(r'\D', '', num)
    if len(digits) > 10 and digits.startswith('1'):
        digits = digits[1:]
    return digits[-10:] if len(digits) >= 10 else digits


def is_voicemail(row):
    return (row.last_app or '').strip().lower() == 'voicemail'


def classify(row, include_outbound=False):
    """Return (did, customer) per the seeder rules, or (None, None) to skip."""
    if not row.extension_number:
        return None, None
    if row.billsec <= 0:
        return None, None
    if is_voicemail(row):
        return None, None
    if row.direction == 'inbound':
        return row.destination_number, row.caller_id_number
    if row.direction == 'outbound' and include_outbound:
        return row.caller_id_number, row.destination_number
    return None, None


def run(tenant_code, limit, did_filter, include_outbound):
    try:
        tenant = Tenant.objects.get(tenant_code=tenant_code)
    except Tenant.DoesNotExist:
        print(f"ERROR: Tenant '{tenant_code}' not found.")
        sys.exit(1)

    qs = (XmlCdr.objects
          .filter(tenant=tenant)
          .order_by('start_stamp'))

    total = qs.count()
    print(f"Tenant: {tenant_code}  ({total} XmlCdr rows)\n")

    # Tally why rows get skipped, so you can spot data-quality issues.
    skip_counts = defaultdict(int)
    accepted = 0

    # affinity_map[(did_norm, customer_norm)] = {ext, last_seen, count, last_did_raw, last_customer_raw}
    affinity = {}

    for row in qs.iterator(chunk_size=2000):
        if not row.extension_number:
            skip_counts['no_extension'] += 1
            continue
        if row.billsec <= 0:
            skip_counts['billsec_zero'] += 1
            continue
        if is_voicemail(row):
            skip_counts['voicemail'] += 1
            continue
        if row.direction == 'outbound' and not include_outbound:
            skip_counts['outbound_excluded'] += 1
            continue
        if row.direction not in ('inbound', 'outbound'):
            skip_counts[f'direction_{row.direction}'] += 1
            continue

        did_raw, cust_raw = classify(row, include_outbound=include_outbound)
        if not did_raw or not cust_raw:
            skip_counts['missing_did_or_customer'] += 1
            continue

        did_n = normalize_number(did_raw)
        cust_n = normalize_number(cust_raw)
        if not did_n or not cust_n:
            skip_counts['unnormalizable'] += 1
            continue

        accepted += 1
        key = (did_n, cust_n)
        existing = affinity.get(key)
        if existing is None or row.start_stamp > existing['last_seen']:
            affinity[key] = {
                'extension': row.extension_number,
                'last_seen': row.start_stamp,
                'last_did_raw': did_raw,
                'last_customer_raw': cust_raw,
                'last_direction': row.direction,
                'count': (existing['count'] + 1) if existing else 1,
            }
        else:
            existing['count'] += 1

    print(f"Accepted rows : {accepted}")
    print(f"Unique mappings: {len(affinity)}")
    print(f"Skipped:")
    for reason, n in sorted(skip_counts.items(), key=lambda x: -x[1]):
        print(f"  {reason:30s} {n}")
    print()

    # Filter + sort for display
    rows = sorted(affinity.items(), key=lambda kv: kv[1]['last_seen'], reverse=True)
    if did_filter:
        did_n = normalize_number(did_filter)
        rows = [r for r in rows if r[0][0] == did_n]
        print(f"Filtered to DID {did_filter} (normalized {did_n}): {len(rows)} mappings\n")

    print(f"{'last_seen':20s}  {'DID (norm)':12s}  {'customer (norm)':16s}  {'ext':6s}  {'dir':9s}  calls  raw DID -> raw customer")
    print('-' * 130)
    for (did_n, cust_n), info in rows[:limit]:
        ts = info['last_seen'].strftime('%Y-%m-%d %H:%M:%S') if info['last_seen'] else '(none)'
        print(f"{ts}  {did_n:12s}  {cust_n:16s}  {info['extension']:6s}  {info['last_direction']:9s}  {info['count']:5d}  {info['last_did_raw']} -> {info['last_customer_raw']}")

    if len(rows) > limit:
        print(f"\n... {len(rows) - limit} more (use --limit to see more)")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Preview caller-extension affinity from existing XmlCdr rows.')
    parser.add_argument('--tenant', required=True, help='Tenant code, e.g. GMD')
    parser.add_argument('--limit', type=int, default=50, help='Max mappings to print (default 50)')
    parser.add_argument('--did', default='', help='Filter to a single DID (raw or normalized)')
    parser.add_argument('--include-outbound', action='store_true', help='Also seed from outbound rows (legacy data may misattribute the agent)')
    args = parser.parse_args()
    run(args.tenant, args.limit, args.did, args.include_outbound)
