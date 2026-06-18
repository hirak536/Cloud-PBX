#!/usr/bin/env python3
"""
import_extensions_api.py — standalone Django script to bulk-import extensions
pulled directly from the legacy PBX OpenAPI (instead of a CSV).

Usage (run from backend/):
    python import_extensions_api.py --tenant IHS \
        --api-url https://sip5.houstonsupport.com/pbx/openapi.php/extensions \
        --api-tenant IHS --api-key SECRET [--dry-run] [--update]

The API returns a JSON array of objects:
    { "id": 3970, "number": "1000", "name": "Gireesh SIngh", "tech": "PJSIP" }

It does NOT include passwords, so we generate a fresh 16-char password for each
extension using the SAME scheme as the frontend (Extensions.jsx::generatePassword):
at least one uppercase, one lowercase, one digit, then 13 more alphanumeric chars,
all shuffled. Passwords are guaranteed unique within this run.
"""

"""
cd /opt/IHS-PBX/backend
python sip2fs_migration/import_extensions_api.py \
  --tenant DLDC \
  --api-key LKUfiY8hG8r5szxQ \
  --dry-run
"""

import os
import sys
import secrets
import argparse
import urllib.parse
import urllib.request
import json
import django

# ── Bootstrap Django ──────────────────────────────────────────────────────────
# backend/ is the Django import root (holds config/, core/, apps/); this script lives in backend/sip2fs_migration/
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.dev')
django.setup()

from core.models import Tenant, Domain
from apps.extensions.models import Extension
from apps.destinations.models import Destination


# Default OpenAPI base — both /extensions and /dids hang off this. Override with --api-base.
DEFAULT_API_BASE = 'https://sip5.houstonsupport.com/pbx/openapi.php'


# ── Legacy → local fax_protocol mapping ─────────────────────────────────────────
# Legacy di_faxprotocol: '' / 'f' (force/analog). Local choices are t38-centric.
def map_fax_protocol(legacy: str) -> str:
    return {'f': 't38_preferred'}.get((legacy or '').strip(), 't38_only')


# ── Password generation — mirrors frontend Extensions.jsx::generatePassword ─────
# (uses secrets instead of Math.random for cryptographic quality; same structure)
_UPPER = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
_LOWER = 'abcdefghijklmnopqrstuvwxyz'
_DIGIT = '0123456789'
_ALL = _UPPER + _LOWER + _DIGIT


def generate_password(seen: set) -> str:
    """16-char password: >=1 upper, >=1 lower, >=1 digit, 13 random, shuffled.
    Retries until it produces one not already in `seen` (avoids duplicates)."""
    while True:
        chars = [
            secrets.choice(_UPPER),
            secrets.choice(_LOWER),
            secrets.choice(_DIGIT),
            *[secrets.choice(_ALL) for _ in range(13)],
        ]
        # Fisher-Yates shuffle, same as the frontend
        for i in range(len(chars) - 1, 0, -1):
            j = secrets.randbelow(i + 1)
            chars[i], chars[j] = chars[j], chars[i]
        pwd = ''.join(chars)
        if pwd not in seen:
            seen.add(pwd)
            return pwd


def fetch_json(endpoint: str, api_tenant: str, api_key: str):
    query = urllib.parse.urlencode({'tenant': api_tenant, 'key': api_key})
    url = f"{endpoint}?{query}"
    req = urllib.request.Request(url, headers={'Accept': 'application/json'})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode('utf-8'))


def import_dids(api_base, api_tenant, api_key, tenant, domain, dry_run, allow_update):
    endpoint = api_base.rstrip('/') + '/dids'
    try:
        rows = fetch_json(endpoint, api_tenant, api_key)
    except Exception as e:
        print(f"ERROR: failed to fetch DIDs from API: {e}")
        return

    print(f"\nFetched {len(rows)} DID(s) from API\n")

    created = updated = skipped = 0
    errors = []
    seen_numbers = set()

    for i, row in enumerate(rows, start=1):
        # Build E.164 from country + area + number (digits only, then prefix +)
        country = str(row.get('di_country') or '').strip()
        area = str(row.get('di_area') or '').strip()
        local = str(row.get('di_number') or '').strip()
        digits = f"{country}{area}{local}"
        if not local:
            msg = f"DID {i}: skipped — missing number"
            print(f"  SKIP  {msg}")
            errors.append(msg)
            skipped += 1
            continue
        number = '+' + digits

        # Dedup within this run (the API can list the same number twice)
        if number in seen_numbers:
            print(f"  SKIP  DID {i}: {number} — duplicate within feed")
            skipped += 1
            continue
        seen_numbers.add(number)

        comment = (row.get('di_comment') or '').strip()
        name = (row.get('name') or comment or local).strip()

        # Fax mapping — legacy di_fax: no/auto/force/storeandforward/forcedirect...
        di_fax = (row.get('di_fax') or 'no').strip().lower()
        fax_receive = di_fax not in ('', 'no')
        fax_emails = (row.get('di_fax_email') or '').strip()
        fields = dict(
            tenant=tenant,
            domain=domain,
            destination_name=name,
            destination_description=comment,
            destination_enabled=True,
            fax_receive=fax_receive,
            fax_station_id=(row.get('di_faxstationid') or '').strip(),
            fax_protocol=map_fax_protocol(row.get('di_faxprotocol')),
            fax_email_destinations=fax_emails,
            fax_store=str(row.get('di_fax_store') or '').strip().lower() == 'yes',
            use_cnam_service=str(row.get('di_cnam') or '').strip().lower() == 'on',
        )

        existing = Destination.objects.filter(destination_number=number).first()
        if existing:
            if not allow_update:
                print(f"  SKIP  DID {i}: {number} already exists (use --update to overwrite)")
                skipped += 1
                continue
            if not dry_run:
                for k, v in fields.items():
                    setattr(existing, k, v)
                existing.save()
            print(f"  UPDATE DID {i}: {number} — {name}")
            updated += 1
        else:
            if not dry_run:
                Destination.objects.create(destination_number=number, **fields)
            print(f"  CREATE DID {i}: {number} — {name}")
            created += 1

    print()
    print(f"DIDs done — created: {created}, updated: {updated}, skipped: {skipped}, errors: {len(errors)}")
    if errors:
        print("\nDID errors:")
        for e in errors:
            print(f"  {e}")


def run(api_base, api_tenant, api_key, tenant_code, dry_run, allow_update,
        do_extensions=True, do_dids=True):
    api_base = api_base.rstrip('/')
    try:
        tenant = Tenant.objects.get(tenant_code=tenant_code)
    except Tenant.DoesNotExist:
        print(f"ERROR: Tenant with code '{tenant_code}' not found.")
        sys.exit(1)

    # Resolve domain (same logic as import_dids.py / Extension.save)
    domain = (
        tenant.domains.filter(domain_enabled=True).first()
        or Domain.objects.filter(domain_universal=True, domain_enabled=True).first()
        or Domain.objects.filter(domain_enabled=True).first()
    )

    print(f"Tenant : {tenant}")
    print(f"Domain : {domain}")
    print(f"Source : {api_base} (tenant={api_tenant})")
    print(f"Mode   : {'DRY RUN — no changes written' if dry_run else 'LIVE'}")
    print(f"Update : {'yes (existing records will be overwritten)' if allow_update else 'no (existing records will be skipped)'}")
    print()

    if do_dids:
        import_dids(api_base, api_tenant, api_key, tenant, domain, dry_run, allow_update)

    if not do_extensions:
        return

    try:
        rows = fetch_json(api_base + '/extensions', api_tenant, api_key)
    except Exception as e:
        print(f"ERROR: failed to fetch extensions from API: {e}")
        sys.exit(1)

    print(f"\nFetched {len(rows)} extension(s) from API\n")

    created = updated = skipped = 0
    errors = []
    seen_pwds = set()

    for i, row in enumerate(rows, start=1):
        number = str(row.get('number') or '').strip()
        name = (row.get('name') or '').strip()

        if not number:
            msg = f"Item {i}: skipped — missing number"
            print(f"  SKIP  {msg}")
            errors.append(msg)
            skipped += 1
            continue

        if not name:
            print(f"  SKIP  Item {i}: extension {number} — blank name, skipping")
            skipped += 1
            continue

        password = generate_password(seen_pwds)
        username = f"{number}-{tenant_code}"
        vm_dest = f'voicemail:{number}'

        existing = Extension.objects.filter(tenant=tenant, extension=number).first()

        if existing:
            if not allow_update:
                print(f"  SKIP  Item {i}: extension {number} already exists (use --update to overwrite)")
                skipped += 1
                continue
            if not dry_run:
                existing.password = password
                existing.effective_caller_id_name = name or existing.effective_caller_id_name
                existing.sip_username = username or existing.sip_username
                existing.save()
            print(f"  UPDATE Item {i}: {number} ({name})")
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
            print(f"  CREATE Item {i}: {number} ({name})")
            created += 1

    print()
    print(f"Done — created: {created}, updated: {updated}, skipped: {skipped}, errors: {len(errors)}")
    if errors:
        print("\nErrors:")
        for e in errors:
            print(f"  {e}")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Import extensions from the legacy PBX OpenAPI into a tenant.')
    parser.add_argument('--tenant', required=True, help='Local tenant code, e.g. IHS')
    parser.add_argument('--api-key', required=True, help='key query param for the API')
    parser.add_argument('--api-base', default=DEFAULT_API_BASE,
                        help=f'OpenAPI base URL (default: {DEFAULT_API_BASE}). /extensions and /dids are appended.')
    parser.add_argument('--api-tenant', default=None,
                        help='tenant query param for the API (default: same as --tenant)')
    parser.add_argument('--dry-run', action='store_true', help='Preview changes without writing to the database')
    parser.add_argument('--update', action='store_true', help='Overwrite existing records (default: skip)')
    parser.add_argument('--extensions-only', action='store_true', help='Import only extensions (skip DIDs)')
    parser.add_argument('--dids-only', action='store_true', help='Import only DIDs (skip extensions)')
    args = parser.parse_args()

    do_extensions = not args.dids_only
    do_dids = not args.extensions_only
    api_tenant = args.api_tenant or args.tenant

    run(args.api_base, api_tenant, args.api_key, args.tenant, args.dry_run, args.update,
        do_extensions=do_extensions, do_dids=do_dids)
