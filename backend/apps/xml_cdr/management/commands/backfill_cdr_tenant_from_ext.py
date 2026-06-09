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

        from django.db.models import Q

        code_to_tenant = {t.tenant_code: t for t in Tenant.objects.all()}
        valid = set(code_to_tenant)

        # Pass 1 — any field carrying a "-TENANTCODE" suffix.
        orphans = XmlCdr.objects.filter(tenant__isnull=True).filter(
            Q(extension_number__contains='-') | Q(destination_number__contains='-')
        ).only('xml_cdr_uuid', 'extension_number', 'destination_number')

        self.stdout.write(f'Pass 1: scanning rows with a dash in ext/destination...')
        by_code = {}
        for row in orphans.iterator(chunk_size=2000):
            for field in (row.extension_number, row.destination_number):
                if field and '-' in field:
                    code = field.rsplit('-', 1)[-1]
                    if code in valid:
                        by_code.setdefault(code, []).append(row.xml_cdr_uuid)
                        break

        updated = 0
        for code, uuids in by_code.items():
            if dry_run:
                self.stdout.write(f'  WOULD set tenant={code} on {len(uuids)} rows')
                updated += len(uuids)
                continue
            tenant = code_to_tenant[code]
            for i in range(0, len(uuids), 1000):
                with transaction.atomic():
                    updated += XmlCdr.objects.filter(xml_cdr_uuid__in=uuids[i:i + 1000]).update(tenant=tenant)
            self.stdout.write(self.style.SUCCESS(f'  set tenant={code} on {len(uuids)} rows'))

        # Pass 2 — B-legs inherit the tenant of their A-leg (matched by bridge_uuid).
        self.stdout.write('Pass 2: B-leg → A-leg tenant inheritance...')
        bleg_updated = 0
        bleg_orphans = XmlCdr.objects.filter(
            tenant__isnull=True, bridge_uuid__isnull=False
        ).only('xml_cdr_uuid', 'bridge_uuid').iterator(chunk_size=2000)
        for row in bleg_orphans:
            a_tenant_id = XmlCdr.objects.filter(
                call_uuid=row.bridge_uuid, tenant__isnull=False
            ).values_list('tenant_id', flat=True).first()
            if a_tenant_id:
                if dry_run:
                    bleg_updated += 1
                else:
                    XmlCdr.objects.filter(xml_cdr_uuid=row.xml_cdr_uuid).update(tenant_id=a_tenant_id)
                    bleg_updated += 1
        verb = 'would update' if dry_run else 'updated'
        self.stdout.write(self.style.SUCCESS(f'  B-leg inheritance: {verb} {bleg_updated} rows'))

        self.stdout.write(self.style.SUCCESS(f'Done: {verb} {updated + bleg_updated} rows total.'))
