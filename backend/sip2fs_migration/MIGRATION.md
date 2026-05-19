# GMD Tenant Migration Guide

## Prerequisites
- Backend venv activated: `source venv/bin/activate` (Linux) or `.\venv\Scripts\activate` (Windows)
- Run all commands from `backend/` directory
- API key: `trL9cGpdP6WW9Y9z`

---

## Step 1 — Import Extensions

**Source file:** `sip_migration/GMD/Ext/export-20260519.csv`
**Columns:** `Number, Name, Username, Password`

```bash
# Dry run
python import_extensions.py ..\sip_migration\GMD\Ext\export-20260519.csv --tenant GMD --dry-run

# Live import
python import_extensions.py ..\sip_migration\GMD\Ext\export-20260519.csv --tenant GMD
```

**Notes:**
- Extensions with blank Name are skipped automatically
- Each extension is created with voicemail enabled
- Forwarding enabled: Busy / No Answer / Not Registered → own voicemail
- Voicemail box is auto-created by post_save signal
- If tenant hits `max_extensions` limit, update it first:
  ```bash
  python -c "
  import os, django
  os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings.dev'
  django.setup()
  from core.models import Tenant
  t = Tenant.objects.get(tenant_code='GMD')
  t.max_extensions = 200
  t.save()
  print('Updated:', t.max_extensions)
  "
  ```
- To overwrite existing extensions: add `--update` flag

---

## Step 2 — Import DIDs

**Source file:** `sip_migration/GMD/Did/export-20260519 (1).csv`
**Columns:** `Number, Comment`

```bash
# Dry run
python import_dids.py "..\sip_migration\GMD\Did\export-20260519 (1).csv" --tenant GMD --dry-run

# Live import
python import_dids.py "..\sip_migration\GMD\Did\export-20260519 (1).csv" --tenant GMD
```

**Notes:**
- Numbers are automatically normalized to E.164 format (`+1XXXXXXXXXX`)
- DIDs are created with no destination assigned — assign routing in the UI after import
- To overwrite existing DIDs: add `--update` flag

---

## Step 3 — Migrate Voicemail Audio

**Must be run on the FreeSWITCH server** (writes audio files to local disk).

```bash
# Dry run (safe — no files downloaded, no DB writes)
python migrate_voicemails.py --tenant GMD --key trL9cGpdP6WW9Y9z --dry-run --workers 20

# Live migration
python migrate_voicemails.py --tenant GMD --key trL9cGpdP6WW9Y9z --workers 20
```

**Notes:**
- Workers controls parallel downloads — 20 is safe on 1Gbps, reduce to 10 if API errors occur
- Extensions with no voicemail messages are skipped automatically (reported as SKIPPED)
- Already-migrated messages are skipped on re-run (idempotent)
- Audio saved to: `/var/lib/freeswitch/storage/voicemail/default/<domain>/<voicemail_uuid>/msg_<uuid>.wav`
- `Old` folder messages → marked as read; `INBOX` messages → marked as unread
- Transcription is NOT triggered on migrated messages

**If re-running after a failed/empty migration, clean up bad records first:**
```bash
python -c "
import os, django
os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings.dev'
django.setup()
from apps.voicemails.models import VoicemailMessage
msgs = VoicemailMessage.objects.using('voicemail_sqlite').filter(forwarded_by__startswith='legacy:')
count = msgs.count()
for m in msgs:
    if m.file_path and os.path.isfile(m.file_path) and os.path.getsize(m.file_path) == 0:
        os.remove(m.file_path)
msgs.delete()
print(f'Deleted {count} bad records')
"
```

---

## Migration Results (GMD — 2026-05-19)

| Step | Result |
|------|--------|
| Extensions imported | 93 |
| Extensions skipped (blank name) | 15 |
| DIDs imported | 31 |
| Voicemails migrated | 589 |
| Voicemails skipped (no messages) | 65 |
| Errors | 0 |

Report file: `/opt/IHS-PBX/backend/voicemail_migration_report_GMD_1779190888.csv`

---

## Utility Scripts

| Script | Purpose |
|--------|---------|
| `check_tenant_domain.py` | Check domain linkage for a tenant |
| `check_dids.py` | Verify DIDs in DB and patch missing domain |
| `check_col.py` | Check DB column definitions |
