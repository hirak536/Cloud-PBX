#!/usr/bin/env python3
"""
migrate_voicemails.py — migrate voicemail audio from legacy Asterisk PBX to FreeSWITCH.

For each extension in the tenant:
  1. Fetch message list from legacy API
  2. Skip extensions with no messages (null/empty response)
  3. For each message: download audio, save to FreeSWITCH storage, insert voicemail_msgs row
  4. Write a report CSV

Usage (run from backend/):
    python migrate_voicemails.py --tenant GMD --key <api_key> [--workers 5] [--dry-run]

Storage layout (mirrors FreeSWITCH convention):
    /var/lib/freeswitch/storage/voicemail/default/<domain>/<voicemail_uuid>/msg_<uuid>.wav

voicemail_msgs username = voicemail_uuid  (matches generators.py convention)
"""

import os
import sys
import csv
import uuid
import time
import argparse
import threading
import django
import requests
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.dev')
django.setup()

from core.models import Tenant
from apps.extensions.models import Extension
from apps.voicemails.models import Voicemail, VoicemailMessage

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
log = logging.getLogger(__name__)

API_BASE = 'https://sip5.houstonsupport.com/pbx/proxyapi.php'
STORAGE_BASE = '/var/lib/freeswitch/storage/voicemail/default'

# Thread-safe print lock
_print_lock = threading.Lock()

def tprint(*args, **kwargs):
    with _print_lock:
        print(*args, **kwargs)


def fetch_messages(key, tenant_code, mailbox):
    try:
        r = requests.get(API_BASE, params={
            'key': key,
            'reqtype': 'VOICEMAIL',
            'tenant': tenant_code,
            'mailbox': mailbox,
            'action': 'messages',
            'format': 'json',
        }, timeout=30)
        r.raise_for_status()
        data = r.json()
        if not data or not isinstance(data, list):
            return None
        return data
    except Exception as exc:
        log.warning('fetch_messages %s failed: %s', mailbox, exc)
        return None


def download_audio(key, tenant_code, msg_id, mailbox, dest_path, dry_run):
    if dry_run:
        return True
    try:
        r = requests.get(API_BASE, params={
            'key': key,
            'reqtype': 'VOICEMAIL',
            'action': 'message',
            'tenant': tenant_code,
            'msgid': msg_id,
            'mailbox': mailbox,
        }, timeout=60, stream=True)
        r.raise_for_status()
        # Reject empty responses (API returns 200 with 0 bytes on error)
        if int(r.headers.get('Content-Length', 1)) == 0:
            log.warning('download_audio %s returned empty response', msg_id)
            return False
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
        with open(dest_path, 'wb') as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
        # Verify file is not empty
        if os.path.getsize(dest_path) == 0:
            os.remove(dest_path)
            return False
        return True
    except Exception as exc:
        log.warning('download_audio %s failed: %s', msg_id, exc)
        return False


def msg_already_migrated(msg_id):
    return VoicemailMessage.objects.using('voicemail_sqlite').filter(forwarded_by=f'legacy:{msg_id}').exists()


def insert_voicemail_msg(vm_uuid_str, domain_name, file_path, msg, new_uuid, dry_run):
    raw_cid = msg.get('callerid', '')
    cid_name = ''
    cid_number = ''
    if '<' in raw_cid and '>' in raw_cid:
        cid_name = raw_cid.split('<')[0].strip().strip('"')
        cid_number = raw_cid.split('<')[1].rstrip('>')
    else:
        cid_number = raw_cid

    created_epoch = int(msg.get('origtime', int(time.time())))
    duration = int(msg.get('duration', 0))

    raw_dir = msg.get('dir', '')
    if '/INBOX' in raw_dir:
        in_folder = 'inbox'
    elif '/Old' in raw_dir:
        in_folder = 'Old'
    else:
        in_folder = 'inbox'

    if not dry_run:
        VoicemailMessage.objects.using('voicemail_sqlite').create(
            uuid=new_uuid,
            created_epoch=created_epoch,
            read_epoch=created_epoch if in_folder == 'Old' else 0,
            username=vm_uuid_str,
            domain=domain_name,
            cid_name=cid_name,
            cid_number=cid_number,
            in_folder=in_folder,
            file_path=file_path,
            message_len=duration,
            flags='',
            read_flags='read' if in_folder == 'Old' else '',
            forwarded_by=f'legacy:{msg.get("msg_id", "")}',
        )
    return in_folder


def process_extension(ext, tenant, tenant_code, api_key, domain_name, dry_run):
    """Process one extension — returns list of report row dicts."""
    rows = []
    ext_num = ext.extension
    name = ext.effective_caller_id_name

    vm = Voicemail.objects.filter(tenant=tenant, voicemail_id=ext_num).first()
    if not vm:
        if dry_run:
            vm_uuid_str = f'dry-run-{ext_num}'
        else:
            rows.append({'extension': ext_num, 'name': name, 'status': 'SKIPPED',
                         'msg_id': '', 'new_uuid': '', 'folder': '', 'duration': '',
                         'note': 'No voicemail box found'})
            return rows
    else:
        vm_uuid_str = str(vm.voicemail_uuid)

    storage_dir = os.path.join(STORAGE_BASE, domain_name, vm_uuid_str)

    messages = fetch_messages(api_key, tenant_code, ext_num)
    if not messages:
        rows.append({'extension': ext_num, 'name': name, 'status': 'SKIPPED',
                     'msg_id': '', 'new_uuid': '', 'folder': '', 'duration': '',
                     'note': 'No messages'})
        return rows

    tprint(f"  Ext {ext_num} ({name}): {len(messages)} messages")

    for msg in messages:
        legacy_msg_id = msg.get('msg_id', '')

        if not dry_run and msg_already_migrated(legacy_msg_id):
            rows.append({'extension': ext_num, 'name': name, 'status': 'ALREADY_DONE',
                         'msg_id': legacy_msg_id, 'new_uuid': '', 'folder': msg.get('dir', ''),
                         'duration': msg.get('duration', ''), 'note': 'Already migrated'})
            continue

        new_uuid_str = str(uuid.uuid4())
        dest_path = os.path.join(storage_dir, f'msg_{new_uuid_str}.wav')

        ok = download_audio(api_key, tenant_code, legacy_msg_id, ext_num, dest_path, dry_run)
        if not ok:
            rows.append({'extension': ext_num, 'name': name, 'status': 'ERROR',
                         'msg_id': legacy_msg_id, 'new_uuid': '', 'folder': msg.get('dir', ''),
                         'duration': msg.get('duration', ''), 'note': 'Audio download failed'})
            continue

        try:
            folder = insert_voicemail_msg(vm_uuid_str, domain_name, dest_path, msg, new_uuid_str, dry_run)
            tprint(f"    {'[DRY] ' if dry_run else ''}MIGRATED {ext_num} msg {legacy_msg_id} → {new_uuid_str} [{folder}]")
            rows.append({'extension': ext_num, 'name': name, 'status': 'MIGRATED',
                         'msg_id': legacy_msg_id, 'new_uuid': new_uuid_str, 'folder': folder,
                         'duration': msg.get('duration', ''), 'note': ''})
        except Exception as exc:
            log.exception('msg %s DB insert failed', legacy_msg_id)
            rows.append({'extension': ext_num, 'name': name, 'status': 'ERROR',
                         'msg_id': legacy_msg_id, 'new_uuid': '', 'folder': msg.get('dir', ''),
                         'duration': msg.get('duration', ''), 'note': str(exc)})

    return rows


def run(tenant_code, api_key, dry_run, workers):
    try:
        tenant = Tenant.objects.get(tenant_code=tenant_code)
    except Tenant.DoesNotExist:
        print(f"ERROR: Tenant '{tenant_code}' not found.")
        sys.exit(1)

    from core.models import Domain
    domain = (
        tenant.domains.filter(domain_enabled=True).first()
        or Domain.objects.filter(domain_universal=True, domain_enabled=True).first()
        or Domain.objects.filter(domain_enabled=True).first()
    )
    domain_name = domain.domain_name if domain else None
    if not domain_name:
        if dry_run:
            domain_name = 'dry-run.local'
            print(f"WARNING: No domain found — using placeholder '{domain_name}' for dry run")
        else:
            print("ERROR: No enabled domain found for tenant.")
            sys.exit(1)

    print(f"Tenant  : {tenant}")
    print(f"Domain  : {domain_name}")
    print(f"Mode    : {'DRY RUN' if dry_run else 'LIVE'}")
    print(f"Workers : {workers}")
    print()

    extensions = list(Extension.objects.filter(
        tenant=tenant, voicemail_enabled=True, enabled=True
    ).order_by('extension'))
    print(f"Extensions to process: {len(extensions)}")
    print()

    all_rows = []

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(process_extension, ext, tenant, tenant_code, api_key, domain_name, dry_run): ext
            for ext in extensions
        }
        for future in as_completed(futures):
            ext = futures[future]
            try:
                rows = future.result()
                all_rows.extend(rows)
            except Exception as exc:
                log.exception('Unexpected error processing ext %s', ext.extension)
                all_rows.append({
                    'extension': ext.extension, 'name': ext.effective_caller_id_name,
                    'status': 'ERROR', 'msg_id': '', 'new_uuid': '', 'folder': '',
                    'duration': '', 'note': str(exc),
                })

    # Sort report by extension for readability
    all_rows.sort(key=lambda r: r['extension'])

    migrated  = sum(1 for r in all_rows if r['status'] == 'MIGRATED')
    skipped   = sum(1 for r in all_rows if r['status'] in ('SKIPPED', 'ALREADY_DONE'))
    errors    = sum(1 for r in all_rows if r['status'] == 'ERROR')

    report_path = os.path.join(
        BASE_DIR,
        f'voicemail_migration_report_{tenant_code}_{int(time.time())}.csv'
    )
    fieldnames = ['extension', 'name', 'status', 'msg_id', 'new_uuid', 'folder', 'duration', 'note']
    with open(report_path, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(all_rows)

    print()
    print(f"Done — migrated: {migrated}, skipped: {skipped}, errors: {errors}")
    print(f"Report : {report_path}")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Migrate voicemail audio from legacy PBX to FreeSWITCH.')
    parser.add_argument('--tenant', required=True, help='Tenant code, e.g. GMD')
    parser.add_argument('--key', required=True, help='Legacy API key')
    parser.add_argument('--workers', type=int, default=5, help='Number of parallel workers (default: 5)')
    parser.add_argument('--dry-run', action='store_true', help='Preview without downloading or writing to DB')
    args = parser.parse_args()

    run(args.tenant, args.key, args.dry_run, args.workers)
