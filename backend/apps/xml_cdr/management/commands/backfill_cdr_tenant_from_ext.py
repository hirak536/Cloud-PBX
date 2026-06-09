"""
Management command: backfill_cdr_tenant_from_ext

Assigns tenant to CDR rows that landed with tenant=NULL but carry the tenant
code in extension_number (e.g. "600-GMD"). These come from WebRTC outbound
calls that arrive with an empty context and a DID as caller_id_number, so the
ingest-time tenant resolution misses them — but extension_number has the code.

Usage:
    python manage.py backfill_cdr_tenant_from_ext --dry-run
    python manage.py backfill_cdr_tenant_from_ext
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.xml_cdr.models import XmlCdr
from core.models import Tenant


class Command(BaseCommand):
    help = 'Backfill tenant on CDR rows using the tenant code in extension_number.'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true',
                            help='Report what would change without writing.')

    def handle(self, *args, **options):
        dry_run = options['dry_run']

        code_to_tenant = {t.tenant_code: t for t in Tenant.objects.all()}

        orphans = XmlCdr.objects.filter(
            tenant__isnull=True, extension_number__contains='-'
        ).only('xml_cdr_uuid', 'extension_number')

        total = orphans.count()
        self.stdout.write(f'Found {total} tenant=NULL CDR rows with a dash in extension_number.')

        by_code = {}
        for row in orphans.iterator(chunk_size=1000):
            code = row.extension_number.rsplit('-', 1)[-1]
            if code in code_to_tenant:
                by_code.setdefault(code, []).append(row.xml_cdr_uuid)

        updated = 0
        for code, uuids in by_code.items():
            if dry_run:
                self.stdout.write(f'  WOULD set tenant={code} on {len(uuids)} rows')
                updated += len(uuids)
                continue
            tenant = code_to_tenant[code]
            # Update in batches to keep transactions small.
            for i in range(0, len(uuids), 1000):
                batch = uuids[i:i + 1000]
                with transaction.atomic():
                    n = XmlCdr.objects.filter(xml_cdr_uuid__in=batch).update(tenant=tenant)
                    updated += n
            self.stdout.write(self.style.SUCCESS(f'  set tenant={code} on {len(uuids)} rows'))

        verb = 'would update' if dry_run else 'updated'
        self.stdout.write(self.style.SUCCESS(f'Done: {verb} {updated} rows.'))
