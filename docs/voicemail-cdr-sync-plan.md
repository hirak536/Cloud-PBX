# Voicemail ↔ CDR Sync (delete voicemail → remove call from logs)

**Status:** planned, not implemented
**Decision:** when a voicemail message is deleted, **hard-delete** its matching CDR row(s). Link the two via `call_uuid`. Applies to **future** voicemails only (existing ones have no link and are a safe no-op on delete).

---

## Why this is needed

There is currently **no link** between a voicemail message and its CDR row:

- `VoicemailMessage` (`apps/voicemails/models.py`) has no `call_uuid` / `xml_cdr_uuid`.
- `XmlCdr` (`apps/xml_cdr/models.py`) has no voicemail-message reference.
- The voicemail ingest endpoint never receives `call_uuid` from FreeSWITCH.
- A CDR is only *guessed* to be voicemail via `last_app` heuristics
  (`last_app='system' AND last_arg CONTAINS 'voicemail-messages/ingest'`, etc.).
- The only existing correlation is the fuzzy temporal+caller match in
  `apps/xml_cdr/management/commands/backfill_voicemail_cdrs.py` — proof there is
  no native link.

## Why the link lives in a NEW Postgres table (not on the voicemail row)

`voicemail_msgs` is a **FreeSWITCH-owned SQLite table** (`db_table='voicemail_msgs'`,
DB alias `voicemail_sqlite`, path `/var/lib/freeswitch/db/voicemail_default.db`).
FreeSWITCH (`mod_voicemail`) reads/writes and may recreate/validate its schema, so
adding a column there is unsafe and won't migrate cleanly. The codebase already
solved this exact problem for read-state with a separate Postgres table
(`VoicemailReadState`). Follow that pattern.

---

## Implementation steps

### 1. Dialplan — pass `call_uuid` into the voicemail ingest
- File: `freeswitch_config/generators.py` (voicemail ingest `curl_cmd`, ~line 871–880)
- Add to the curl: `-F call_uuid=${call_uuid}`
- `${call_uuid}` is the inbound A-leg's channel uuid (matches the CDR A-leg's `call_uuid`).
- After deploy: regenerate dialplan + flush dialplan cache (`dialplan:xml:*`).

### 2. New Postgres model `VoicemailCallLink`
- File: `apps/voicemails/models.py` (next to `VoicemailReadState`)
- Fields:
  - `message_uuid` — CharField(255), primary_key (the voicemail message uuid)
  - `call_uuid` — CharField(64), db_index=True
  - `created_at` — DateTimeField(auto_now_add=True)
- `db_table = 'voicemail_call_link'`
- Router: **no change needed.** `freeswitch_config/routers.py` only routes
  `voicemailmessage` / `voicemailprefs` to SQLite; `voicemailcalllink` falls
  through to `default` (Postgres), which is correct.

### 3. Migration
- `python manage.py makemigrations voicemails` → normal migration on the default
  (Postgres) DB. Then `migrate`. (Clean — unlike the FreeSWITCH-owned tables.)

### 4. Ingest endpoint — write the link
- File: `apps/voicemails/views.py` — the `/api/v1/voicemail-messages/ingest/`
  view (the `get_or_create` on `VoicemailMessage`, ~line 256–271).
- Read `call_uuid = request.data.get('call_uuid')` (or POST).
- If non-empty:
  `VoicemailCallLink.objects.update_or_create(message_uuid=uuid_val, defaults={'call_uuid': call_uuid})`
- Guard: if `call_uuid` missing/empty, skip silently (don't break ingest).

### 5. Delete endpoints — hard-delete the matching CDR
Two delete paths, update **both**:

- **Client API:** `apps/client_api/views.py` `ClientVoicemailMessageView.delete()` (~1100)
  - Already has `tenant` in scope.
- **Admin:** `apps/voicemails/views.py` `VoicemailMessageViewSet.destroy()` (~166)
  - Resolve tenant from the message's domain/mailbox first.

In each, AFTER the message row + audio file are deleted:
1. `link = VoicemailCallLink.objects.filter(message_uuid=msg.uuid).first()`
2. If `link`:
   - `XmlCdr.objects.filter(tenant=<tenant>).filter(Q(call_uuid=link.call_uuid) | Q(bridge_uuid=link.call_uuid)).delete()`
     - Tenant-scoped so a `call_uuid` collision can't delete another tenant's row.
     - Include `bridge_uuid` so the bridge B-leg(s) of the same call go too (whole
       call disappears, not just one leg). Decide A-leg-only vs both at build time.
   - `link.delete()`
3. If no link (pre-existing voicemail): do nothing to CDR — safe no-op.

---

## Notes / things to watch

- **Counts impact (accepted):** hard-delete shrinks answered/missed/voicemail
  totals and removes the call from history. Irreversible. Reports will reflect it.
- **A-leg vs B-leg:** voicemail `call_uuid` matches the inbound A-leg; including
  `bridge_uuid` removes the paired bridge legs too. Confirm desired scope.
- **Retroactive:** existing voicemails have no link row → deleting them won't
  touch any CDR. Only voicemails created after step 1 ships will sync. (A one-time
  fuzzy backfill to populate `VoicemailCallLink` for old messages is possible
  later, reusing the logic in `backfill_voicemail_cdrs.py`, but is out of scope.)
- **Tenant resolution on admin delete:** the SQLite `VoicemailMessage` has no
  tenant FK — resolve via `username` (voicemail_uuid) → `Voicemail` → tenant, or
  via `domain` → tenant, before scoping the CDR delete.

---

## Files touched (summary)
| File | Change |
|------|--------|
| `freeswitch_config/generators.py` | add `-F call_uuid=${call_uuid}` to voicemail ingest curl |
| `apps/voicemails/models.py` | new `VoicemailCallLink` model |
| `apps/voicemails/migrations/00XX_*.py` | create `voicemail_call_link` table |
| `apps/voicemails/views.py` | ingest writes link; `destroy()` deletes matching CDR |
| `apps/client_api/views.py` | `ClientVoicemailMessageView.delete()` deletes matching CDR |
