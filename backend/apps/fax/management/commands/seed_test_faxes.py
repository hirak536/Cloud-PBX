"""Seed test fax listing entries for the IHDT tenant.

Inserts a batch of FaxFile rows for tenant_code='IHDT', all marked completed
('sent' outbound / 'received' inbound) and dated today. Every seeded row is
tagged with a marker in fax_file_station_id so the --revert flag can delete
exactly what this command created — real fax records are never touched.

Usage:
    python manage.py seed_test_faxes            # insert test faxes
    python manage.py seed_test_faxes --count 20 # insert a specific number
    python manage.py seed_test_faxes --revert   # delete only seeded rows
"""
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.fax.models import FaxFile
from core.models import Tenant

TENANT_CODE = 'IHDT'
# Marker written into fax_file_station_id; revert targets only these rows.
SEED_MARKER = 'SEED_TEST_FAX'


class Command(BaseCommand):
    help = 'Seed completed test fax listing entries for the IHDT tenant (or revert them).'

    def add_arguments(self, parser):
        parser.add_argument('--count', type=int, default=10,
                            help='Number of test fax entries to create (default: 10).')
        parser.add_argument('--revert', action='store_true',
                            help='Delete all seeded test fax entries instead of creating them.')

    def handle(self, *args, **options):
        try:
            tenant = Tenant.objects.get(tenant_code=TENANT_CODE)
        except Tenant.DoesNotExist:
            raise CommandError(f"Tenant with tenant_code='{TENANT_CODE}' not found.")

        if options['revert']:
            return self._revert(tenant)
        return self._seed(tenant, options['count'])

    @transaction.atomic
    def _seed(self, tenant, count):
        now = timezone.now()
        created = []
        for i in range(count):
            inbound = i % 3 == 0  # mix directions; ~1/3 inbound
            fax = FaxFile.objects.create(
                tenant=tenant,
                fax_file_type='pdf',
                fax_file_name=f'{SEED_MARKER}_{i + 1:03d}.pdf',
                fax_file_path='',
                direction='inbound' if inbound else 'outbound',
                fax_file_status='received' if inbound else 'sent',
                fax_file_pages=(i % 5) + 1,
                fax_file_duration=30 + i * 5,
                fax_file_caller_id_name=f'Test Sender {i + 1}',
                fax_file_caller_id_number=f'+1713555{1000 + i:04d}',
                fax_file_destination_number=f'+1281555{2000 + i:04d}',
                fax_file_station_id=SEED_MARKER,  # revert marker
                fax_file_date=now,
            )
            created.append(fax)
        self.stdout.write(self.style.SUCCESS(
            f'Created {len(created)} completed test fax entries for tenant '
            f'{TENANT_CODE}, dated {now:%Y-%m-%d}.'))

    def _revert(self, tenant):
        qs = FaxFile.objects.filter(tenant=tenant, fax_file_station_id=SEED_MARKER)
        deleted, _ = qs.delete()
        self.stdout.write(self.style.SUCCESS(
            f'Reverted (deleted) {deleted} seeded test fax entries for tenant {TENANT_CODE}.'))
