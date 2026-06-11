"""
backfill_cdr_direction — fix mislabeled `direction` on historical CDR rows.

Why this exists
---------------
Gateway-bound legs written by mod_xml_cdr often land with direction='inbound'
even when an internal extension placed an outbound PSTN call. The CDR ingest
view now classifies "internal extension -> NANP number" as outbound, but rows
ingested before that fix keep the wrong value.

This command applies the SAME safe rule retroactively, scoped tightly to avoid
false positives:
  - caller_id_number is a real extension whose suffix is a KNOWN tenant_code
    (e.g. 901-IHDT, 201-SIS) — bare/garbage callers like 0, 90001, 101-admin
    are excluded;
  - destination_number is a clean NANP number (10 digits, or 11 leading with 1).
Then a second pass flips any B-leg whose bridged A-leg is outbound.

Idempotent. Safe to re-run.

Usage:
    python manage.py backfill_cdr_direction --dry-run
    python manage.py backfill_cdr_direction
"""
from django.core.management.base import BaseCommand
from django.db import connection, transaction

from core.models import Tenant


class Command(BaseCommand):
    help = 'Fix direction on historical v_xml_cdr rows (internal ext -> PSTN = outbound).'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true',
                            help='Report what would change without writing.')

    def handle(self, *args, **options):
        dry_run = options['dry_run']

        codes = sorted(c for c, _ in Tenant.objects.values_list('tenant_code', 'tenant_uuid') if c)
        if not codes:
            self.stderr.write('No tenant codes found — nothing to do.')
            return
        suffix_re = '-(' + '|'.join(codes) + ')$'

        # caller is a known-tenant extension; destination is a NANP PSTN number.
        where = (
            "direction <> 'outbound' "
            "AND caller_id_number ~ %(sfx)s "
            "AND regexp_replace(destination_number, '^[+]', '') ~ '^1?[0-9]{10}$'"
        )
        params = {'sfx': suffix_re}

        with connection.cursor() as cur:
            cur.execute(f"SELECT count(*) FROM v_xml_cdr WHERE {where}", params)
            ext_count = cur.fetchone()[0]
        self.stdout.write(f'Ext->PSTN rows to flip to outbound: {ext_count}')

        if dry_run:
            with connection.cursor() as cur:
                cur.execute("""
                    SELECT count(*)
                    FROM v_xml_cdr b
                    JOIN v_xml_cdr a ON a.call_uuid = b.bridge_uuid AND a.leg = 'a'
                    WHERE b.direction <> 'outbound'
                      AND b.bridge_uuid IS NOT NULL
                      AND a.direction = 'outbound'
                """)
                bridge_count = cur.fetchone()[0]
            self.stdout.write(self.style.WARNING(
                f'DRY RUN — would flip {ext_count} via ext->PSTN, '
                f'~{bridge_count} B-legs via A-leg inheritance (more may cascade). '
                f'No changes written.'
            ))
            return

        with transaction.atomic(), connection.cursor() as cur:
            cur.execute(f"UPDATE v_xml_cdr SET direction = 'outbound' WHERE {where}", params)
            updated = cur.rowcount
        self.stdout.write(self.style.SUCCESS(f'Flipped {updated} rows via ext->PSTN rule.'))

        # Second pass: any B-leg whose bridged A-leg is now outbound is outbound too.
        inherited_total = 0
        while True:
            with transaction.atomic(), connection.cursor() as cur:
                cur.execute("""
                    UPDATE v_xml_cdr b
                    SET direction = 'outbound'
                    FROM v_xml_cdr a
                    WHERE b.direction <> 'outbound'
                      AND b.bridge_uuid IS NOT NULL
                      AND a.call_uuid = b.bridge_uuid
                      AND a.leg = 'a'
                      AND a.direction = 'outbound'
                """)
                n = cur.rowcount
            inherited_total += n
            self.stdout.write(f'  A-leg inheritance pass: flipped {n} rows')
            if n == 0:
                break
        if inherited_total:
            self.stdout.write(self.style.SUCCESS(
                f'Flipped {inherited_total} B-legs via A-leg inheritance.'
            ))
