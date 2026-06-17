"""
backfill_outbound_cid — recover the presented DID on outbound CDR rows.

Why this exists
---------------
Outbound CDRs stored caller_id_number from FreeSWITCH's raw `caller_id_number`
channel variable, which on a WebRTC A-leg is the SIP username (e.g. "905-IHDT")
— not the number actually presented to the carrier. The presented DID lives in
`effective_caller_id_number` (set by the dialplan / X-OverrideCID). The ingest
now prefers the effective value for new outbound calls, but historical rows
still carry the extension label.

This command recovers the real DID for affected rows by matching each CDR's
call_uuid to its dialplan trace in the FreeSWITCH logs and reading the LAST
`effective_caller_id_number` SET for that channel (the override-applied value).

Scope & limits
--------------
- Only outbound rows whose caller_id_number looks like an extension label
  (^\\d+-[A-Za-z]+$) are candidates.
- Only calls whose logs still exist can be recovered; rows older than the log
  retention window are left untouched (genuinely unrecoverable).
- Only DID-shaped recovered values (digits, optional leading +) are applied;
  anything else is skipped so we never replace a label with another label.

Idempotent: re-running only touches rows that still have a label-shaped CID.
A real run first writes a backup CSV (xml_cdr_uuid, old caller_id_number).

Usage:
    python manage.py backfill_outbound_cid --dry-run
    python manage.py backfill_outbound_cid --backup /tmp/cid_backfill_backup.csv
"""
import csv
import glob
import os
import re

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.xml_cdr.models import XmlCdr

LABEL_RE = re.compile(r'^\d+-[A-Za-z]+$')
DID_RE = re.compile(r'^\+?\d{7,15}$')
# Matches:  ... [effective_caller_id_number]=[+13468310770]
EFF_RE = re.compile(r'\[effective_caller_id_number\]=\[([^\]]*)\]')
# The channel UUID is the first whitespace-delimited token on FreeSWITCH log lines.
UUID_RE = re.compile(r'^([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})\b')


class Command(BaseCommand):
    help = 'Recover presented DID on historical outbound CDR rows from FreeSWITCH logs.'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true',
                            help='Report what would change without writing.')
        parser.add_argument('--log-glob', default='/var/log/freeswitch/freeswitch.log*',
                            help='Glob for FreeSWITCH log files to scan.')
        parser.add_argument('--backup', default='',
                            help='CSV path to write (xml_cdr_uuid, old caller_id_number) before updating.')
        parser.add_argument('--batch-size', type=int, default=2000)

    def handle(self, *args, **opts):
        dry = opts['dry_run']

        # 1. Which rows need fixing?
        candidates = list(
            XmlCdr.objects.filter(direction='outbound',
                                  caller_id_number__regex=r'^[0-9]+-[A-Za-z]+$',
                                  call_uuid__isnull=False)
            .values_list('xml_cdr_uuid', 'call_uuid', 'caller_id_number')
        )
        if not candidates:
            self.stdout.write('No label-shaped outbound CIDs to backfill. Nothing to do.')
            return
        wanted = {str(call_uuid) for _, call_uuid, _ in candidates}
        self.stdout.write(f'Candidate outbound rows with label CID: {len(candidates)}')
        self.stdout.write(f'Distinct call_uuids to find in logs: {len(wanted)}')

        # 2. Scan logs once, building {call_uuid -> last DID-shaped effective CID}.
        log_files = sorted(glob.glob(opts['log_glob']))
        self.stdout.write(f'Scanning {len(log_files)} log file(s)...')
        found = {}
        for path in log_files:
            try:
                with open(path, 'r', errors='replace') as fh:
                    for line in fh:
                        if 'effective_caller_id_number' not in line:
                            continue
                        um = UUID_RE.match(line)
                        if not um:
                            continue
                        cu = um.group(1)
                        if cu not in wanted:
                            continue
                        em = EFF_RE.search(line)
                        if not em:
                            continue
                        val = em.group(1).strip()
                        if val and DID_RE.match(val):
                            # last write wins (override-applied value)
                            found[cu] = val
            except OSError as e:
                self.stderr.write(f'  skip {path}: {e}')
        self.stdout.write(f'Resolved DID from logs for {len(found)} call_uuid(s).')

        # 3. Build the update list (only where recovered value differs and is a DID).
        updates = []  # (xml_cdr_uuid, old, new)
        for xid, call_uuid, old in candidates:
            new = found.get(str(call_uuid))
            if new and new != old:
                updates.append((xid, old, new))

        recoverable = len(updates)
        unrecoverable = len(candidates) - recoverable
        self.stdout.write(self.style.NOTICE(
            f'Recoverable: {recoverable}   |   Not recoverable (no log match): {unrecoverable}'))
        for xid, old, new in updates[:10]:
            self.stdout.write(f'  {xid}  {old}  ->  {new}')
        if recoverable > 10:
            self.stdout.write(f'  ... and {recoverable - 10} more')

        if dry:
            self.stdout.write(self.style.WARNING('DRY RUN — no changes written.'))
            return

        if not updates:
            self.stdout.write('Nothing to update.')
            return

        # 4. Backup before writing.
        backup = opts['backup'] or f'/tmp/cid_backfill_{timezone.now():%Y%m%d_%H%M%S}.csv'
        with open(backup, 'w', newline='') as fh:
            w = csv.writer(fh)
            w.writerow(['xml_cdr_uuid', 'old_caller_id_number', 'new_caller_id_number'])
            for xid, old, new in updates:
                w.writerow([xid, old, new])
        self.stdout.write(self.style.SUCCESS(f'Backup written: {backup}'))

        # 5. Apply in batches.
        bs = opts['batch_size']
        done = 0
        for i in range(0, len(updates), bs):
            chunk = updates[i:i + bs]
            with transaction.atomic():
                for xid, _old, new in chunk:
                    XmlCdr.objects.filter(xml_cdr_uuid=xid).update(caller_id_number=new)
            done += len(chunk)
            self.stdout.write(f'  updated {done}/{len(updates)}')
        self.stdout.write(self.style.SUCCESS(f'Done. Updated {done} rows. Backup at {backup}'))
