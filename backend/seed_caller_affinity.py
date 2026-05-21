#!/usr/bin/env python3
"""
seed_caller_affinity.py — one-time manual seed for caller-extension affinity.

Reads a CSV with one of these header formats:
    customer,extension
    phone_number,sip_extname        (extension may be "411-GMD" — suffix stripped)

Upserts each row into v_caller_extension_affinity for the given tenant.
Existing rows are only overwritten if the seed timestamp (--as-of, default now)
is newer than the stored last_seen, so this is safe to re-run.

Usage:
    python seed_caller_affinity.py --tenant GMD --csv seed.csv
    python seed_caller_affinity.py --tenant GMD --csv seed.csv --dry-run
    python seed_caller_affinity.py --tenant GMD --csv seed.csv --as-of 2026-01-01
"""
import os
import sys
import csv
import argparse
import django
from datetime import datetime, timezone as dt_timezone

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.dev')
django.setup()

from core.models import Tenant, Domain
from apps.custom_destinations.affinity import upsert_affinity, normalize_number
from apps.custom_destinations.models import CallerExtensionAffinity


def run(tenant_code, csv_path, as_of, dry_run):
    try:
        tenant = Tenant.objects.get(tenant_code=tenant_code)
    except Tenant.DoesNotExist:
        print(f"ERROR: Tenant '{tenant_code}' not found.")
        sys.exit(1)

    domain = (
        tenant.domains.filter(domain_enabled=True).first()
        or Domain.objects.filter(domain_universal=True, domain_enabled=True).first()
    )

    print(f"Tenant : {tenant_code}")
    print(f"Domain : {domain.domain_name if domain else '(none)'}")
    print(f"CSV    : {csv_path}")
    print(f"As-of  : {as_of.isoformat()}")
    print(f"Mode   : {'DRY RUN' if dry_run else 'LIVE'}")
    print()

    inserted = 0
    updated = 0
    skipped_older = 0
    bad = 0

    with open(csv_path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        cols_lower = {c.lower() for c in (reader.fieldnames or [])}
        # Accept either (customer, extension) or (phone_number, sip_extname).
        if {'customer', 'extension'}.issubset(cols_lower):
            cust_key, ext_key = 'customer', 'extension'
        elif {'phone_number', 'sip_extname'}.issubset(cols_lower):
            cust_key, ext_key = 'phone_number', 'sip_extname'
        else:
            print(f"ERROR: CSV must have columns (customer, extension) or "
                  f"(phone_number, sip_extname). Got: {reader.fieldnames}")
            sys.exit(1)

        def _pick(row, key):
            for k in (key, key.capitalize(), key.upper()):
                v = row.get(k)
                if v is not None:
                    return v
            return ''

        for i, row in enumerate(reader, start=2):
            customer = _pick(row, cust_key).strip()
            ext_raw = _pick(row, ext_key).strip()
            # Strip tenant suffix: "411-GMD" -> "411", "Voicemail 506" -> blank (handled later).
            ext = ext_raw.split('-', 1)[0].strip() if ext_raw else ''
            if not customer or not ext:
                bad += 1
                print(f"  line {i}: SKIP missing field  customer={customer!r} ext={ext!r}")
                continue

            cust_n = normalize_number(customer)
            if not cust_n:
                bad += 1
                print(f"  line {i}: SKIP unnormalizable  customer={customer!r}")
                continue

            existing = CallerExtensionAffinity.objects.filter(
                tenant=tenant, caller_number=cust_n,
            ).first()

            if dry_run:
                if existing and as_of <= existing.last_seen:
                    skipped_older += 1
                    print(f"  line {i}: WOULD SKIP (existing newer)  {cust_n} -> ext {existing.extension_number}  (seed ext {ext})")
                elif existing:
                    updated += 1
                    print(f"  line {i}: WOULD UPDATE  {cust_n}: {existing.extension_number} -> {ext}")
                else:
                    inserted += 1
                    print(f"  line {i}: WOULD INSERT  {cust_n} -> ext {ext}")
                continue

            before_ts = existing.last_seen if existing else None
            obj = upsert_affinity(
                tenant=tenant, customer=cust_n, extension=ext,
                when=as_of, domain=domain, source='manual_seed',
            )
            if not obj:
                bad += 1
                continue
            if not existing:
                inserted += 1
                print(f"  line {i}: INSERT  {cust_n} -> ext {ext}")
            elif obj.last_seen != before_ts:
                updated += 1
                print(f"  line {i}: UPDATE  {cust_n} -> ext {ext}")
            else:
                skipped_older += 1
                print(f"  line {i}: SKIP (existing newer)  {cust_n} keeps ext {obj.extension_number}")

    print()
    print(f"Done — inserted={inserted}  updated={updated}  skipped_older={skipped_older}  bad={bad}")


if __name__ == '__main__':
    p = argparse.ArgumentParser(description='One-time seed of caller-extension affinity from a CSV.')
    p.add_argument('--tenant', required=True, help='Tenant code, e.g. GMD')
    p.add_argument('--csv', required=True, help='Path to CSV with columns: customer,extension')
    p.add_argument('--as-of', default=None,
                   help='Timestamp to record as last_seen (YYYY-MM-DD). Default: now.')
    p.add_argument('--dry-run', action='store_true', help='Preview without writing')
    args = p.parse_args()

    if args.as_of:
        as_of = datetime.strptime(args.as_of, '%Y-%m-%d').replace(tzinfo=dt_timezone.utc)
    else:
        as_of = datetime.now(tz=dt_timezone.utc)

    run(args.tenant, args.csv, as_of, args.dry_run)
