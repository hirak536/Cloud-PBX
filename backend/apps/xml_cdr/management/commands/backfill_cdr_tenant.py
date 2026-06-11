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
            with connection.cursor() as cur:
                cur.execute("""
                    SELECT count(*)
                    FROM v_xml_cdr b
                    JOIN v_xml_cdr a ON a.call_uuid = b.bridge_uuid
                    WHERE b.tenant_uuid IS NULL
                      AND b.bridge_uuid IS NOT NULL
                      AND a.tenant_uuid IS NOT NULL
                """)
                bridge_count = cur.fetchone()[0]
            self.stdout.write(self.style.WARNING(
                f'DRY RUN — would update {total} rows via suffix match, '
                f'~{bridge_count} via bridge inheritance (more may cascade). No changes written.'
            ))
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
        self.stdout.write(self.style.SUCCESS(f'Updated {updated} rows via suffix match.'))

        # Second pass: inherit tenant from the bridged A-leg. A B-leg (e.g. a
        # gateway-bound leg) often carries no resolvable suffix, but its
        # bridge_uuid points at the A-leg channel, which already has a tenant.
        # Loop because a freshly-filled A-leg can in turn supply its own B-leg.
        inherited_total = 0
        while True:
            with transaction.atomic(), connection.cursor() as cur:
                cur.execute("""
                    UPDATE v_xml_cdr b
                    SET tenant_uuid = a.tenant_uuid
                    FROM v_xml_cdr a
                    WHERE b.tenant_uuid IS NULL
                      AND b.bridge_uuid IS NOT NULL
                      AND a.call_uuid = b.bridge_uuid
                      AND a.tenant_uuid IS NOT NULL
                """)
                n = cur.rowcount
            inherited_total += n
            self.stdout.write(f'  bridge-inheritance pass: filled {n} rows')
            if n == 0:
                break
        if inherited_total:
            self.stdout.write(self.style.SUCCESS(
                f'Updated {inherited_total} rows via bridge_uuid A-leg inheritance.'
            ))

        # Third pass: DID match. Unanswered WebRTC ring-group forks (and similar
        # legs) carry no suffix and their bridge A-leg is never posted, but the
        # tenant's own DID sits in caller_id_number or destination_number. Match
        # those against v_destinations on the last 10 digits so +1XXXXXXXXXX /
        # 1XXXXXXXXXX / XXXXXXXXXX all line up.
        #
        # SELECT the candidate UUIDs first (read-only), then UPDATE in small
        # batches keyed on xml_cdr_uuid — never a single table-wide UPDATE, which
        # deadlocks against concurrent live FreeSWITCH CDR inserts on v_xml_cdr.
        with connection.cursor() as cur:
            cur.execute("""
                WITH did AS (
                    SELECT tenant_uuid,
                           right(regexp_replace(destination_number,'\\D','','g'), 10) AS d10
                    FROM v_destinations
                    WHERE tenant_uuid IS NOT NULL
                      AND length(regexp_replace(destination_number,'\\D','','g')) >= 10
                )
                SELECT c.xml_cdr_uuid, did.tenant_uuid
                FROM v_xml_cdr c
                JOIN did ON did.d10 IN (
                    right(regexp_replace(COALESCE(c.destination_number,''),'\\D','','g'), 10),
                    right(regexp_replace(COALESCE(c.caller_id_number,''),'\\D','','g'), 10)
                )
                WHERE c.tenant_uuid IS NULL
            """)
            did_rows = cur.fetchall()

        did_by_tenant = {}
        for xml_cdr_uuid, tenant_uuid in did_rows:
            did_by_tenant.setdefault(str(tenant_uuid), []).append(xml_cdr_uuid)

        did_total = 0
        for tenant_uuid, uuids in did_by_tenant.items():
            for i in range(0, len(uuids), batch_size):
                chunk = uuids[i:i + batch_size]
                with transaction.atomic(), connection.cursor() as cur:
                    cur.execute(
                        "UPDATE v_xml_cdr SET tenant_uuid = %s "
                        "WHERE xml_cdr_uuid = ANY(%s) AND tenant_uuid IS NULL",
                        [tenant_uuid, chunk],
                    )
                    did_total += cur.rowcount
        if did_total:
            self.stdout.write(self.style.SUCCESS(
                f'Updated {did_total} rows via DID match on caller/destination number.'
            ))

        # Re-run bridge inheritance: DID-filled A-legs can now seed their B-legs.
        while True:
            with transaction.atomic(), connection.cursor() as cur:
                cur.execute("""
                    UPDATE v_xml_cdr b
                    SET tenant_uuid = a.tenant_uuid
                    FROM v_xml_cdr a
                    WHERE b.tenant_uuid IS NULL
                      AND b.bridge_uuid IS NOT NULL
                      AND a.call_uuid = b.bridge_uuid
                      AND a.tenant_uuid IS NOT NULL
                """)
                n = cur.rowcount
            if n == 0:
                break
            self.stdout.write(f'  post-DID bridge-inheritance pass: filled {n} rows')
