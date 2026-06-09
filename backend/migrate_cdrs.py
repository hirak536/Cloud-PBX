#!/usr/bin/env python3
"""
migrate_cdrs.py — migrate Call Detail Records from legacy Asterisk PBX to FreeSWITCH.

Pulls CDR records from the legacy proxyapi in date-range chunks and inserts them
into the v_xml_cdr table. Deduplicates by uniqueid — only one record is kept per
call (the leg with the longest billsec wins, fallback to longest duration).

Usage (run from backend/):
    python migrate_cdrs.py --tenant GMD --key <api_key> \
        --start 2026-05-12 --end 2026-05-19 [--chunk-days 7] [--dry-run]

The script processes the date range in chunks (default 7 days) to avoid huge API
responses. Each chunk is fetched, deduplicated, then inserted.
"""

import os
import re
import sys
import csv
import time
import argparse
import django
import requests
import logging
from datetime import datetime, timedelta, timezone as dt_timezone

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.dev')
django.setup()

from core.models import Tenant, Domain
from apps.xml_cdr.models import XmlCdr

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
log = logging.getLogger(__name__)

API_BASE = 'https://sip5.houstonsupport.com/pbx/proxyapi.php'


def fetch_cdrs(key, tenant_code, start_dt, end_dt):
    """Fetch CDR records for a date range. Returns list of dicts or [] on error."""
    params = {
        'reqtype': 'INFO',
        'info': 'cdrs',
        'tenant': tenant_code,
        'key': key,
        'format': 'json',
        'start': start_dt.strftime('%Y-%m-%d %H:%M:%S'),
        'end': end_dt.strftime('%Y-%m-%d %H:%M:%S'),
    }
    try:
        r = requests.get(API_BASE, params=params, timeout=180)
        r.raise_for_status()
        data = r.json()
        if not data or not isinstance(data, list):
            return []
        return data
    except Exception as exc:
        log.warning('fetch_cdrs %s..%s failed: %s', start_dt, end_dt, exc)
        return []


def dedupe_by_uniqueid(records):
    """
    Each call may have multiple legs sharing the same uniqueid (e.g. BUSY then ANSWERED).
    Keep one row per uniqueid — prefer the leg with the longest billsec, fallback to duration.
    """
    by_uid = {}
    for rec in records:
        uid = rec.get('uniqueid', '')
        if not uid:
            continue
        if (rec.get('disposition') or '').upper().strip() == 'CONGESTION':
            continue
        existing = by_uid.get(uid)
        if existing is None:
            by_uid[uid] = rec
            continue
        # Tie-break: prefer ANSWERED, then longest billsec, then longest duration
        def _score(r):
            answered = 1 if r.get('disposition') == 'ANSWERED' else 0
            return (answered, int(r.get('billsec') or 0), int(r.get('duration') or 0))
        if _score(rec) > _score(existing):
            by_uid[uid] = rec
    return list(by_uid.values())


def _parse_dt(s):
    """Parse '2026-01-18 21:17:55' → aware datetime. Returns None for '0000-00-00 00:00:00'."""
    if not s or s.startswith('0000'):
        return None
    try:
        return datetime.strptime(s, '%Y-%m-%d %H:%M:%S').replace(tzinfo=dt_timezone.utc)
    except Exception:
        return None


def _split_clid(clid):
    """'\"NAME\" <NUMBER>' → ('NAME', 'NUMBER'). Returns ('', clid) if no angle brackets."""
    if '<' in clid and '>' in clid:
        name = clid.split('<')[0].strip().strip('"')
        number = clid.split('<')[1].rstrip('>')
        return name, number
    return '', clid


_DID_PREFIXES = ('FROMOUT-', 'FROM-', 'OUT-')


def _clean_phone(num):
    """Strip quotes/brackets and non-dial characters from a phone-number-ish string."""
    if not num:
        return ''
    num = re.sub(r'["<>]', '', num)
    num = re.sub(r'[^\d\-() +]', '', num)
    return num.strip()


def _clean_did(dst):
    """Strip known legacy prefixes (FROMOUT-, FROM-, OUT-) then phone-clean."""
    if not dst:
        return ''
    s = dst.strip()
    for pfx in _DID_PREFIXES:
        if s.upper().startswith(pfx):
            s = s[len(pfx):]
            break
    return _clean_phone(s)


def map_record(rec, tenant, domain):
    """Map a legacy CDR record to XmlCdr kwargs. Returns None if record is unusable."""
    uniqueid = rec.get('uniqueid', '')
    if not uniqueid:
        return None

    start_dt = _parse_dt(rec.get('start'))
    if not start_dt:
        return None
    answer_dt = _parse_dt(rec.get('answer'))
    end_dt = _parse_dt(rec.get('end'))

    cid_name, cid_number = _split_clid(rec.get('clid', ''))
    cid_number = _clean_phone(cid_number)

    userfield = (rec.get('userfield') or '').strip('[]').lower()
    if userfield not in ('inbound', 'outbound', 'local'):
        userfield = 'inbound'

    # Status calibration: recover ANSWERED from lastapp+answer; demote AGI to NO ANSWER.
    # CONGESTION is dropped earlier by the caller.
    disposition = (rec.get('disposition') or '').upper().strip()
    lastapp_upper = (rec.get('lastapp') or '').upper().strip()
    has_valid_answer = answer_dt is not None
    if disposition in ('NO ANSWER', 'NOANSWER', 'BUSY'):
        pass  # keep as-is
    elif lastapp_upper == 'DIAL' and has_valid_answer:
        disposition = 'ANSWERED'
    elif lastapp_upper == 'AGI':
        disposition = 'NO ANSWER'

    hangup_map = {
        'ANSWERED': 'NORMAL_CLEARING',
        'NO ANSWER': 'NO_ANSWER',
        'NOANSWER': 'NO_ANSWER',
        'BUSY': 'USER_BUSY',
        'FAILED': 'NORMAL_TEMPORARY_FAILURE',
    }
    hangup_cause = hangup_map.get(disposition, 'NORMAL_CLEARING')

    # Extension number: realsrc for outbound (e.g. 104-IHDT), lastdst for inbound (e.g. 429-GMD).
    if userfield == 'outbound':
        ext_raw = rec.get('realsrc', '') or ''
    else:
        ext_raw = rec.get('lastdst', '') or ''
    # Preserve the full sip_username (e.g. "417-GMD") so affinity routing stores the
    # correct suffixed value. For voicemail legs ("Voicemail 506"), extract just the digits.
    ext_raw = ext_raw.strip()
    if ext_raw.lower().startswith('voicemail'):
        m = re.search(r'\d+', ext_raw)
        ext_num = m.group(0) if m else ''
    else:
        ext_num = ext_raw

    billsec = int(rec.get('billsec') or 0)
    duration = int(rec.get('duration') or 0)

    destination_clean = _clean_did(rec.get('dst', '') or '')
    caller_destination_clean = _clean_did(rec.get('firstdst', '') or '')

    return {
        'tenant': tenant,
        'domain': domain,
        'caller_id_name': cid_name[:128],
        'caller_id_number': cid_number[:32],
        'extension_number': ext_num[:32],
        'destination_number': destination_clean[:32],
        'caller_destination': caller_destination_clean[:32],
        'context': (rec.get('dcontext', '') or '')[:128],
        'start_stamp': start_dt,
        'start_epoch': int(start_dt.timestamp()) if start_dt else 0,
        'answer_stamp': answer_dt,
        'answer_epoch': int(answer_dt.timestamp()) if answer_dt else 0,
        'end_stamp': end_dt,
        'end_epoch': int(end_dt.timestamp()) if end_dt else 0,
        'duration': duration,
        'billsec': billsec,
        'direction': userfield,
        'missed_call': (disposition != 'ANSWERED' and userfield == 'inbound'),
        'hangup_cause': hangup_cause,
        'last_app': (rec.get('lastapp', '') or '')[:64],
        'last_arg': (uniqueid or '')[:1024],   # store legacy uniqueid for dedup on re-run
    }


def already_imported(uniqueid):
    """Check if a legacy uniqueid has already been imported (we stash it in last_arg)."""
    return XmlCdr.objects.filter(last_arg=uniqueid).exists()


def already_imported_bulk(uniqueids, tenant):
    """Return the set of uniqueids that already exist in XmlCdr for this tenant."""
    if not uniqueids:
        return set()
    return set(
        XmlCdr.objects
        .filter(tenant=tenant, last_arg__in=list(uniqueids))
        .values_list('last_arg', flat=True)
    )


def process_record(rec, tenant, domain, already_set, dry_run, idx, total):
    """Process one record. Returns a report_rows dict and a status code."""
    uniqueid = rec.get('uniqueid', '')
    prefix = f"  [{idx}/{total}] {uniqueid[:48]:48s}"

    if not uniqueid:
        log.debug(f"{prefix}  SKIP   no uniqueid")
        return {'uniqueid': '', 'status': 'SKIPPED', 'start': rec.get('start', ''),
                'disposition': rec.get('disposition', ''), 'note': 'no uniqueid'}, 'skipped'

    if not dry_run and uniqueid in already_set:
        log.debug(f"{prefix}  DUP    already in XmlCdr")
        return {'uniqueid': uniqueid, 'status': 'ALREADY_DONE', 'start': rec.get('start', ''),
                'disposition': rec.get('disposition', ''), 'note': 'Already imported'}, 'skipped'

    kwargs = map_record(rec, tenant, domain)
    if not kwargs:
        log.debug(f"{prefix}  SKIP   could not map (no start time?)")
        return {'uniqueid': uniqueid, 'status': 'SKIPPED', 'start': rec.get('start', ''),
                'disposition': rec.get('disposition', ''), 'note': 'Could not map record (missing start time?)'}, 'skipped'

    try:
        if not dry_run:
            XmlCdr.objects.create(**kwargs)
        log.debug(
            f"{prefix}  OK     {kwargs['direction']:8s} {kwargs['caller_id_number']:>14s} -> "
            f"{kwargs['destination_number']:14s} ext={kwargs['extension_number'] or '-':6s} "
            f"bs={kwargs['billsec']:>4d} {kwargs['hangup_cause']}"
        )
        return {'uniqueid': uniqueid, 'status': 'INSERTED', 'start': rec.get('start', ''),
                'disposition': rec.get('disposition', ''), 'note': ''}, 'inserted'
    except Exception as exc:
        log.exception(f"{prefix}  ERROR  {exc}")
        return {'uniqueid': uniqueid, 'status': 'ERROR', 'start': rec.get('start', ''),
                'disposition': rec.get('disposition', ''), 'note': str(exc)}, 'error'


def run(tenant_code, api_key, start_date, end_date, chunk_days, dry_run, wipe=False, workers=1, verbose=False):
    try:
        tenant = Tenant.objects.get(tenant_code=tenant_code)
    except Tenant.DoesNotExist:
        print(f"ERROR: Tenant '{tenant_code}' not found.")
        sys.exit(1)

    domain = (
        tenant.domains.filter(domain_enabled=True).first()
        or Domain.objects.filter(domain_universal=True, domain_enabled=True).first()
        or Domain.objects.filter(domain_enabled=True).first()
    )
    if not domain:
        print("ERROR: No enabled domain found.")
        sys.exit(1)

    print(f"Tenant : {tenant}")
    print(f"Domain : {domain.domain_name}")
    print(f"Range  : {start_date} → {end_date}")
    print(f"Chunk  : {chunk_days} days")
    print(f"Mode   : {'DRY RUN' if dry_run else 'LIVE'}")
    if wipe:
        existing = XmlCdr.objects.filter(tenant=tenant).count()
        print(f"Wipe   : YES — will delete {existing} existing XmlCdr rows for tenant {tenant_code}")
        if not dry_run:
            deleted, _ = XmlCdr.objects.filter(tenant=tenant).delete()
            print(f"         deleted {deleted} rows")
    print()

    report_rows = []
    total_fetched = 0
    total_inserted = 0
    total_skipped = 0
    total_dedup_removed = 0

    cursor = start_date
    while cursor < end_date:
        chunk_end = min(cursor + timedelta(days=chunk_days), end_date)
        # API expects inclusive end, so subtract 1s to avoid duplicate boundary records
        api_end = chunk_end - timedelta(seconds=1)
        print(f"  Fetching {cursor.strftime('%Y-%m-%d %H:%M')} → {api_end.strftime('%Y-%m-%d %H:%M')}")

        records = fetch_cdrs(api_key, tenant_code, cursor, api_end)
        total_fetched += len(records)

        deduped = dedupe_by_uniqueid(records)
        dedup_removed = len(records) - len(deduped)
        total_dedup_removed += dedup_removed
        print(f"    fetched={len(records)}  unique_calls={len(deduped)}  removed_legs={dedup_removed}")

        # One bulk DB hit instead of N per-row .exists() calls.
        uniqueids = [r.get('uniqueid', '') for r in deduped if r.get('uniqueid')]
        already_set = already_imported_bulk(uniqueids, tenant) if not dry_run else set()
        if already_set:
            log.info(f"    {len(already_set)} of {len(deduped)} already imported, will skip")

        chunk_inserted = 0
        chunk_skipped = 0
        chunk_errors = 0

        if workers > 1:
            from concurrent.futures import ThreadPoolExecutor, as_completed
            with ThreadPoolExecutor(max_workers=workers) as pool:
                futures = {
                    pool.submit(process_record, rec, tenant, domain, already_set, dry_run, i + 1, len(deduped)): rec
                    for i, rec in enumerate(deduped)
                }
                for fut in as_completed(futures):
                    row, outcome = fut.result()
                    report_rows.append(row)
                    if outcome == 'inserted': chunk_inserted += 1
                    elif outcome == 'error':  chunk_errors += 1
                    else:                     chunk_skipped += 1
        else:
            for i, rec in enumerate(deduped):
                row, outcome = process_record(rec, tenant, domain, already_set, dry_run, i + 1, len(deduped))
                report_rows.append(row)
                if outcome == 'inserted': chunk_inserted += 1
                elif outcome == 'error':  chunk_errors += 1
                else:                     chunk_skipped += 1

        total_inserted += chunk_inserted
        total_skipped += chunk_skipped
        print(f"    chunk done: inserted={chunk_inserted}  skipped={chunk_skipped}  errors={chunk_errors}")

        cursor = chunk_end

    # Write report
    report_path = os.path.join(
        BASE_DIR,
        f'cdr_migration_report_{tenant_code}_{int(time.time())}.csv'
    )
    fieldnames = ['uniqueid', 'status', 'start', 'disposition', 'note']
    with open(report_path, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(report_rows)

    print()
    print(f"Done — fetched={total_fetched}, dedup_removed={total_dedup_removed}, inserted={total_inserted}, skipped={total_skipped}")
    print(f"Report : {report_path}")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Migrate CDR records from legacy PBX to FreeSWITCH.')
    parser.add_argument('--tenant', required=True, help='Tenant code, e.g. GMD')
    parser.add_argument('--key', required=True, help='Legacy API key')
    parser.add_argument('--start', required=True, help='Start date (YYYY-MM-DD)')
    parser.add_argument('--end', required=True, help='End date (YYYY-MM-DD, exclusive)')
    parser.add_argument('--chunk-days', type=int, default=7, help='Days per API call (default 7)')
    parser.add_argument('--dry-run', action='store_true', help='Preview without writing to DB')
    parser.add_argument('--wipe', action='store_true', help='Delete all existing XmlCdr rows for this tenant before importing')
    parser.add_argument('--workers', type=int, default=1, help='Parallel insert workers (default 1)')
    parser.add_argument('--verbose', '-v', action='store_true', help='Per-record debug logging')
    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
        log.setLevel(logging.DEBUG)
    # Quiet the noisy urllib3 connection logs even in verbose mode.
    logging.getLogger('urllib3').setLevel(logging.INFO)

    start = datetime.strptime(args.start, '%Y-%m-%d').replace(tzinfo=dt_timezone.utc)
    end = datetime.strptime(args.end, '%Y-%m-%d').replace(tzinfo=dt_timezone.utc)

    run(args.tenant, args.key, start, end, args.chunk_days, args.dry_run, args.wipe, args.workers, args.verbose)
