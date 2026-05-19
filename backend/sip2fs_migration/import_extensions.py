#!/usr/bin/env python3
"""
import_extensions.py — standalone Django script to bulk-import extensions from a CSV file.

Usage (run from backend/):
    python import_extensions.py extensions.csv --tenant GMD [--dry-run] [--update]

CSV columns (header row required):
    Number, Name, Username, Password

    - Number   : extension number (e.g. 401)
    - Name     : full name used as caller ID name
    - Username : SIP username, expected format <number>-<tenant_code> (e.g. 401-GMD)
    - Password : SIP password

The tenant is resolved by --tenant (tenant_code).  If --update is given, existing
extensions for that tenant are overwritten; otherwise they are skipped.
"""

import os
import sys
import csv
import argparse
import django

# ── Bootstrap Django ──────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.dev')
django.setup()

from core.models import Tenant
from apps.extensions.models import Extension


def run(csv_path: str, tenant_code: str, dry_run: bool, allow_update: bool):
    try:
        tenant = Tenant.objects.get(tenant_code=tenant_code)
    except Tenant.DoesNotExist:
        print(f"ERROR: Tenant with code '{tenant_code}' not found.")
        sys.exit(1)

    print(f"Tenant : {tenant}")
    print(f"File   : {csv_path}")
    print(f"Mode   : {'DRY RUN — no changes written' if dry_run else 'LIVE'}")
    print(f"Update : {'yes (existing extensions will be overwritten)' if allow_update else 'no (existing extensions will be skipped)'}")
    print()

    created = updated = skipped = 0
    errors = []

    with open(csv_path, newline='', encoding='utf-8-sig') as fh:
        reader = csv.DictReader(fh)
        for i, row in enumerate(reader, start=2):
            number   = (row.get('Number')   or '').strip()
            name     = (row.get('Name')     or '').strip()
            username = (row.get('Username') or '').strip()
            password = (row.get('Password') or '').strip()

            if not number or not password:
                msg = f"Row {i}: skipped — missing Number or Password"
                print(f"  SKIP  {msg}")
                errors.append(msg)
                skipped += 1
                continue

            if not name:
                print(f"  SKIP  Row {i}: extension {number} — blank name, skipping")
                skipped += 1
                continue

            vm_dest = f'voicemail:{number}'

            existing = Extension.objects.filter(tenant=tenant, extension=number).first()

            if existing:
                if not allow_update:
                    print(f"  SKIP  Row {i}: extension {number} already exists (use --update to overwrite)")
                    skipped += 1
                    continue
                if not dry_run:
                    existing.password = password
                    existing.effective_caller_id_name = name or existing.effective_caller_id_name
                    existing.sip_username = username or existing.sip_username
                    existing.save()
                print(f"  UPDATE Row {i}: {number} ({name})")
                updated += 1
            else:
                if not dry_run:
                    Extension.objects.create(
                        tenant=tenant,
                        extension=number,
                        password=password,
                        effective_caller_id_name=name,
                        effective_caller_id_number=number,
                        directory_full_name=name,
                        voicemail_enabled=True,
                        enabled=True,
                        mobile_push_enabled=False,
                        # Forwarding: active toggle on, route busy/no-answer/offline → own voicemail
                        call_forward_active=True,
                        forward_no_answer_enabled=True,
                        forward_no_answer_destination=vm_dest,
                        forward_busy_enabled=True,
                        forward_busy_destination=vm_dest,
                        forward_user_not_registered_enabled=True,
                        forward_user_not_registered_destination=vm_dest,
                    )
                print(f"  CREATE Row {i}: {number} ({name})")
                created += 1

    print()
    print(f"Done — created: {created}, updated: {updated}, skipped: {skipped}, errors: {len(errors)}")
    if errors:
        print("\nErrors:")
        for e in errors:
            print(f"  {e}")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Import extensions from CSV into a tenant.')
    parser.add_argument('csv', help='Path to the CSV file')
    parser.add_argument('--tenant', required=True, help='Tenant code, e.g. GMD')
    parser.add_argument('--dry-run', action='store_true', help='Preview changes without writing to the database')
    parser.add_argument('--update', action='store_true', help='Overwrite existing extensions (default: skip)')
    args = parser.parse_args()

    run(args.csv, args.tenant, args.dry_run, args.update)
