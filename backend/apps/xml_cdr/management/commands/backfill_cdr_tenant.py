"""
backfill_cdr_tenant — assign tenant_uuid to orphaned CDR rows.

Why this exists
---------------
FreeSWITCH writes CDR rows directly into v_xml_cdr via mod_xml_cdr, bypassing
Django. Those INSERTs populate FreeSWITCH-native columns but never tenant_uuid
(tenant is a Django/FusionPBX-layer concept). This system runs a SINGLE shared
domain with multiple tenants distinguished by a username suffix — e.g.
"201-SIS", "1000-IHDT" — so tenant cannot be derived from the domain.

This command recovers tenant for the rows that DO carry a resolvable suffix in
extension_number / destination_number / caller_id_number (priority in that
order). Rows with no suffix (internal/gateway/carrier traffic such as "9002",
"admin", raw DIDs) are genuinely tenant-less and are left untouched.

Idempotent: only touches rows where tenant_uuid IS NULL. Safe to re-run.

Usage:
    python manage.py backfill_cdr_tenant --dry-run
    python manage.py backfill_cdr_tenant
"""
from django.core.management.base import BaseCommand
from django.db import connection, transaction

from core.models import Tenant


class Command(BaseCommand):
    help = 'Backfill tenant_uuid on orphaned v_xml_cdr rows using the username suffix.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Report what would change without writing.',
        )
        parser.add_argument(
            '--batch-size', type=int, default=5000,
            help='Rows updated per transaction (default 5000).',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        batch_size = options['batch_size']

        # tenant_code (uppercase) -> tenant_uuid. Codes are matched verbatim
        # against the "-CODE" suffix, so compare case-sensitively the same way.
        code_to_uuid = {
            code: str(uuid)
            for code, uuid in Tenant.objects.values_list('tenant_code', 'tenant_uuid')
            if code
        }
        if not code_to_uuid:
            self.stderr.write('No tenant codes found — nothing to do.')
            return

        codes = sorted(code_to_uuid)
        # Postgres regex: "-(CODE1|CODE2|...)$"
        suffix_re = '-(' + '|'.join(codes) + ')$'
        # Capture group that pulls the bare code out of a "...-CODE" value.
        extract_re = r'-([A-Za-z]+)$'

        # Resolve each NULL-tenant row to a code via the first field that has a
        # recognised suffix: extension_number > destination_number > caller_id_number.
        select_sql = f"""
            SELECT xml_cdr_uuid,
                   COALESCE(
                       CASE WHEN extension_number   ~ %(sfx)s THEN substring(extension_number   from %(ext)s) END,
                       CASE WHEN destination_number ~ %(sfx)s THEN substring(destination_number from %(ext)s) END,
                       CASE WHEN caller_id_number   ~ %(sfx)s THEN substring(caller_id_number   from %(ext)s) END
                   ) AS code
            FROM v_xml_cdr
            WHERE tenant_uuid IS NULL
              AND (extension_number   ~ %(sfx)s
                OR destination_number ~ %(sfx)s
                OR caller_id_number   ~ %(sfx)s)
        """
        params = {'sfx': suffix_re, 'ext': extract_re}

        with connection.cursor() as cur:
            cur.execute(select_sql, params)
            rows = cur.fetchall()

        # Group row UUIDs by resolved tenant uuid.
        by_tenant = {}
        unmatched = 0
        for xml_cdr_uuid, code in rows:
            tenant_uuid = code_to_uuid.get(code)
            if not tenant_uuid:
                unmatched += 1
                continue
            by_tenant.setdefault(tenant_uuid, []).append(xml_cdr_uuid)

        total = sum(len(v) for v in by_tenant.values())
        self.stdout.write(f'Resolvable orphaned rows: {len(rows)}')
        for tenant_uuid, uuids in sorted(by_tenant.items(), key=lambda kv: -len(kv[1])):
            self.stdout.write(f'  {tenant_uuid}: {len(uuids)}')
        if unmatched:
            self.stdout.write(self.style.WARNING(
                f'  {unmatched} rows had a suffix with no matching tenant_code (skipped).'
            ))

        if dry_run:
            self.stdout.write(self.style.WARNING(f'DRY RUN — would update {total} rows. No changes written.'))
            return

        updated = 0
        for tenant_uuid, uuids in by_tenant.items():
            for i in range(0, len(uuids), batch_size):
                chunk = uuids[i:i + batch_size]
                with transaction.atomic(), connection.cursor() as cur:
                    cur.execute(
                        "UPDATE v_xml_cdr SET tenant_uuid = %s "
                        "WHERE xml_cdr_uuid = ANY(%s) AND tenant_uuid IS NULL",
                        [tenant_uuid, chunk],
                    )
                    updated += cur.rowcount
        self.stdout.write(self.style.SUCCESS(f'Updated {updated} rows.'))
