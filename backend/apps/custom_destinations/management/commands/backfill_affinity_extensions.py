"""
Management command: backfill_affinity_extensions

Fixes affinity rows that store plain extension numbers (e.g. "417") instead of the
full sip_username (e.g. "417-GMD").  These were written by the CDR migration script
which stripped the tenant suffix.  The Lua routing script doesn't care — it strips
the suffix itself — but it's cleaner to store the canonical form everywhere.

Usage:
    python manage.py backfill_affinity_extensions
    python manage.py backfill_affinity_extensions --dry-run
    python manage.py backfill_affinity_extensions --tenant GMD
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.custom_destinations.models import CallerExtensionAffinity
from apps.extensions.models import Extension


class Command(BaseCommand):
    help = 'Backfill affinity rows that have plain extension numbers to use the full sip_username.'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true',
                            help='Report what would change without writing.')
        parser.add_argument('--tenant', metavar='CODE',
                            help='Limit to a specific tenant code (e.g. GMD).')

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        tenant_code = options.get('tenant')

        # Only rows that look like plain digits (no dash) need fixing.
        qs = CallerExtensionAffinity.objects.filter(
            extension_number__regex=r'^\d+$'
        ).select_related('tenant')

        if tenant_code:
            qs = qs.filter(tenant__tenant_code=tenant_code)

        total = qs.count()
        self.stdout.write(f'Found {total} affinity rows with plain extension numbers.')
        if total == 0:
            return

        # Build a lookup: (tenant_id, plain_ext) → sip_username
        # Pull only extensions that belong to affected tenants and have a dash in sip_username.
        tenant_ids = qs.values_list('tenant_id', flat=True).distinct()
        ext_map = {}
        for ext in Extension.objects.filter(
            tenant_id__in=tenant_ids,
            sip_username__contains='-',
        ).only('tenant_id', 'extension', 'sip_username'):
            ext_map[(str(ext.tenant_id), ext.extension)] = ext.sip_username

        updated = skipped = bad = 0
        to_update = []

        for row in qs.iterator(chunk_size=500):
            key = (str(row.tenant_id), row.extension_number)
            sip_username = ext_map.get(key)
            if not sip_username:
                self.stdout.write(
                    self.style.WARNING(
                        f'  SKIP  caller={row.caller_number}  ext={row.extension_number!r}'
                        f'  tenant={row.tenant_id}  (no matching extension found)'
                    )
                )
                skipped += 1
                continue

            if dry_run:
                self.stdout.write(
                    f'  WOULD UPDATE  caller={row.caller_number}'
                    f'  {row.extension_number!r} → {sip_username!r}'
                )
            else:
                row.extension_number = sip_username
                to_update.append(row)
            updated += 1

        if not dry_run and to_update:
            with transaction.atomic():
                CallerExtensionAffinity.objects.bulk_update(to_update, ['extension_number'], batch_size=500)
            self.stdout.write(self.style.SUCCESS(f'Updated {updated} rows.'))
        elif dry_run:
            self.stdout.write(self.style.SUCCESS(f'Dry run: {updated} rows would be updated, {skipped} skipped.'))
        else:
            self.stdout.write(self.style.SUCCESS(f'Updated {updated} rows, {skipped} skipped.'))
