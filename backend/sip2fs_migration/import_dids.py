#!/usr/bin/env python3
"""
import_dids.py — standalone Django script to bulk-import DIDs from a CSV file.

Usage (run from backend/):
    python import_dids.py path\to\dids.csv --tenant GMD [--dry-run] [--update]

CSV columns (header row required):
    Number, Comment

    - Number  : DID phone number (e.g. 12812470858)
    - Comment : friendly name / description (e.g. "I - Dr Saira Hirani")

DIDs are created as enabled, with no destination assigned (dest_type blank).
Assign routing in the UI after import.
"""

import os
import sys
import csv
import argparse
import django

# backend/ is the Django import root (holds config/, core/, apps/); this script lives in backend/sip2fs_migration/
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.dev')
django.setup()

from core.models import Tenant, Domain
from apps.destinations.models import Destination


def run(csv_path: str, tenant_code: str, dry_run: bool, allow_update: bool):
    try:
        tenant = Tenant.objects.get(tenant_code=tenant_code)
    except Tenant.DoesNotExist:
        print(f"ERROR: Tenant with code '{tenant_code}' not found.")
        sys.exit(1)

    # Resolve domain (same logic as Extension.save)
    domain = (
        tenant.domains.filter(domain_enabled=True).first()
        or Domain.objects.filter(domain_universal=True, domain_enabled=True).first()
        or Domain.objects.filter(domain_enabled=True).first()
    )

    print(f"Tenant : {tenant}")
    print(f"Domain : {domain}")
    print(f"File   : {csv_path}")
    print(f"Mode   : {'DRY RUN — no changes written' if dry_run else 'LIVE'}")
    print(f"Update : {'yes (existing DIDs will be overwritten)' if allow_update else 'no (existing DIDs will be skipped)'}")
    print()

    created = updated = skipped = 0
    errors = []

    with open(csv_path, newline='', encoding='utf-8-sig') as fh:
        reader = csv.DictReader(fh)
        for i, row in enumerate(reader, start=2):
            number  = (row.get('Number')  or '').strip()
            comment = (row.get('Comment') or '').strip()

            if not number:
                msg = f"Row {i}: skipped — missing Number"
                print(f"  SKIP  {msg}")
                errors.append(msg)
                skipped += 1
                continue

            # Normalize to E.164: prepend + if not already present
            if not number.startswith('+'):
                number = '+' + number

            existing = Destination.objects.filter(destination_number=number).first()

            if existing:
                if not allow_update:
                    print(f"  SKIP  Row {i}: {number} already exists (use --update to overwrite)")
                    skipped += 1
                    continue
                if not dry_run:
                    existing.destination_name = comment
                    existing.destination_description = comment
                    existing.tenant = tenant
                    existing.domain = domain
                    existing.save()
                print(f"  UPDATE Row {i}: {number} — {comment}")
                updated += 1
            else:
                if not dry_run:
                    Destination.objects.create(
                        tenant=tenant,
                        domain=domain,
                        destination_number=number,
                        destination_name=comment,
                        destination_description=comment,
                        destination_enabled=True,
                    )
                print(f"  CREATE Row {i}: {number} — {comment}")
                created += 1

    print()
    print(f"Done — created: {created}, updated: {updated}, skipped: {skipped}, errors: {len(errors)}")
    if errors:
        print("\nErrors:")
        for e in errors:
            print(f"  {e}")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Import DIDs from CSV into a tenant.')
    parser.add_argument('csv', help='Path to the CSV file')
    parser.add_argument('--tenant', required=True, help='Tenant code, e.g. GMD')
    parser.add_argument('--dry-run', action='store_true', help='Preview changes without writing to the database')
    parser.add_argument('--update', action='store_true', help='Overwrite existing DIDs (default: skip)')
    args = parser.parse_args()

    run(args.csv, args.tenant, args.dry_run, args.update)
