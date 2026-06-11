"""
backfill_voicemail_cdrs — repair voicemail call-log rows that were clobbered by
a garbage synthetic A-leg.

Why this exists
---------------
Inbound calls that land in voicemail are routed via FreeSWITCH `transfer(...)`.
The voicemail `record` application spawns internal media pseudo-legs whose
destination_number is a session token (e.g. 'vqsairma'), with empty
context/last_app and no resolvable tenant. The CDR ingest used to synthesize an
A-leg from such a B-leg; once the (call_uuid, leg='a') unique constraint
(migration 0009) landed, that garbage synthetic A-leg overwrote the real A-leg,
leaving a single row with tenant=NULL, last_app='' and a token destination.

Such rows are invisible in the tenant-scoped call logs and are not classified as
WENT_TO_VOICEMAIL. This command repairs them by correlating each orphan A-leg to
a row in voicemail_msgs (FreeSWITCH-native) by caller number + timestamp, then
recovering tenant / domain / mailbox from the matched Voicemail.

The ingest-side fix in freeswitch_config/views.py (get_or_create + skip
contentless B-legs) prevents NEW garbage rows; this command cleans up the ones
already written.

Match criteria (tight, to avoid touching the ~880k unrelated scanner CDRs):
  - leg='a', tenant IS NULL, last_app=''
  - destination_number is a 6-10 char lowercase alphanumeric session token
    (NOT all digits, NOT a phone number)
  - a voicemail_msgs row exists from the same caller (last 10 digits of
    cid_number) within [-30s, +180s] of the CDR's start_epoch
  - that message's mailbox (username = voicemail_uuid) resolves to a Voicemail
    with a tenant

Idempotent: re-running skips rows already repaired (tenant no longer NULL).

Usage:
    python manage.py backfill_voicemail_cdrs --dry-run
    python manage.py backfill_voicemail_cdrs
"""
import re

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.xml_cdr.models import XmlCdr
from apps.voicemails.models import VoicemailMessage, Voicemail

_TOKEN_RE = re.compile(r'[a-z0-9]{6,10}')


class Command(BaseCommand):
    help = 'Repair voicemail A-leg CDRs clobbered by a garbage synthetic A-leg.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Report what would change without writing.',
        )
        parser.add_argument(
            '--window-before', type=int, default=30,
            help='Seconds before CDR start to look for a voicemail message (default 30).',
        )
        parser.add_argument(
            '--window-after', type=int, default=180,
            help='Seconds after CDR start to look for a voicemail message (default 180).',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        before = options['window_before']
        after = options['window_after']

        # mailbox uuid (str) -> resolved Voicemail attributes
        vmap = {
            str(v.voicemail_uuid): (v.tenant_id, v.domain_id, v.voicemail_id,
                                    v.tenant.tenant_code if v.tenant else None)
            for v in Voicemail.objects.all()
        }

        # Candidate orphan A-legs: tenant NULL, no last_app, token-like destination.
        candidates = (
            XmlCdr.objects.filter(leg='a', tenant__isnull=True, last_app='')
            .exclude(destination_number='')
        )

        repairs = []   # (xml_cdr_uuid, tenant_id, domain_id, voicemail_id, tenant_code, cid)
        scanned = 0
        for r in candidates.iterator():
            dest = r.destination_number or ''
            if not (_TOKEN_RE.fullmatch(dest) and not dest.isdigit()):
                continue
            scanned += 1
            if not r.start_epoch:
                continue
            cidtail = (r.caller_id_number or '').lstrip('+')[-10:]
            if not cidtail:
                continue
            msg = VoicemailMessage.objects.filter(
                created_epoch__gte=r.start_epoch - before,
                created_epoch__lte=r.start_epoch + after,
                cid_number__contains=cidtail,
            ).first()
            if not msg or msg.username not in vmap:
                continue
            tenant_id, domain_id, voicemail_id, code = vmap[msg.username]
            if not tenant_id:
                continue
            repairs.append((r.xml_cdr_uuid, tenant_id, domain_id, voicemail_id, code, r.caller_id_number))

        self.stdout.write(f'Token-destination orphan A-legs scanned: {scanned}')
        self.stdout.write(f'Correlated to a voicemail message: {len(repairs)}')
        by_tenant = {}
        for _, _, _, _, code, _ in repairs:
            by_tenant[code] = by_tenant.get(code, 0) + 1
        for code, n in sorted(by_tenant.items(), key=lambda kv: -kv[1]):
            self.stdout.write(f'  {code}: {n}')

        if dry_run:
            self.stdout.write(self.style.WARNING(
                f'DRY RUN — would repair {len(repairs)} rows. No changes written.'
            ))
            for u, _, _, vid, code, cid in repairs[:15]:
                self.stdout.write(f'    {u} -> tenant={code} mailbox={vid} from={cid}')
            return

        updated = 0
        for xml_cdr_uuid, tenant_id, domain_id, voicemail_id, code, _ in repairs:
            with transaction.atomic():
                # Re-check tenant IS NULL inside the txn so a concurrent real
                # A-leg ingest is never overwritten by this backfill.
                n = (
                    XmlCdr.objects.filter(xml_cdr_uuid=xml_cdr_uuid, tenant__isnull=True)
                    .update(
                        tenant_id=tenant_id,
                        domain_id=domain_id,
                        destination_number=voicemail_id,
                        extension_number=voicemail_id,
                        last_app='voicemail',
                        last_arg=voicemail_id,
                        direction='inbound',
                    )
                )
                updated += n
        self.stdout.write(self.style.SUCCESS(f'Repaired {updated} voicemail A-leg rows.'))
