# Changelog

All notable changes to IHS-PBX are documented in this file.
Newest entries on top.

## 2026-06-12

### Voicemail Greeting — fixed upload path & added Media File greetings
- Fixed uploaded voicemail greetings never playing. The upload endpoint (`VoicemailViewSet.upload_name`) wrote `recorded_name.wav` to a directory keyed by the **extension number** (e.g. `…/500/`), but the dialplan plays the greeting from the directory keyed by the **voicemail UUID** (e.g. `…/676cf165-…/`). The two never matched, so FreeSWITCH found no file. Upload now writes to the UUID directory the dialplan reads from
- This also fixes a cross-tenant collision risk: two tenants can share extension `500`, and only the per-voicemail UUID directory is unique. (`*95` record-your-name already used the UUID via the per-user `${voicemail_id}` channel variable, so record and playback now agree)
- Migrated the existing ext-500 (GMD) greeting from `…/500/recorded_name.wav` to its UUID directory
- New **Media File greeting** mode: a mailbox can now play a reusable file from the **Media Files** library as its greeting, instead of only the per-mailbox recorded name. Pick the media file from a dropdown in the Voicemail dialog
  - Backend: new `media_file` greeting choice + `voicemail_greeting_recording` FK to `recordings.Recording` (migration `voicemails 0013`); dialplan plays the recording from `FREESWITCH_SOUNDS_DIR`, then the beep, then records the message
  - Note: voicemail greetings live in FreeSWITCH voicemail storage (`/var/lib/freeswitch/storage/voicemail/…`), a separate area from the Media Files library (`FREESWITCH_SOUNDS_DIR`); the new mode lets a mailbox *reference* a library file rather than merging the two stores

### Voicemail Notification — multiple email recipients
- The voicemail notification email field (per-voicemail **and** the extension-level fallback) now accepts a **comma-separated list** of addresses; previously it was a single-address `EmailField`
- Backend: fields changed to `CharField(512)` with a new reusable `core.validators.MultiEmailValidator` (migrations `voicemails 0014`, `extensions 0016`). The Python notification/transcript senders split the list into individual recipients (passing the raw comma string as one recipient would have failed at SMTP), and the dialplan normalises whitespace before emitting FreeSWITCH's comma-separated `vm-mailto`
- Frontend: email inputs switched from `type="email"` (which blocks commas via HTML5 validation) to `type="text"`, with updated placeholder/hint

### Destination Picker — server-side search (covers >100 records)
- Fixed destination dropdowns only ever showing the first 100 of each type and search missing records beyond that page — e.g. searching `500` returned no voicemail when it sat past the first 100 rows. The picker filtered a single 100-row client-side page and never queried the server
- The shared `DestinationPicker` (and the Custom Destinations page's `TargetPicker`) now debounce the query and re-fetch server-side via the existing `searchDestData`, so the search covers every record. Wired into Custom Destinations (fallback + BLF ON/OFF), Call Flows, Extensions, and Ring Groups; backward-compatible where `onSearch` is not supplied

## 2026-06-11

### BLF Toggle (Custom Destinations)
- BLF toggle ON/OFF destinations can now route to **any** destination — extension, IVR, ring group, voicemail, external number, hangup, or another custom destination — instead of only another custom destination. The dialog now uses the same route dropdown (`DestinationPicker`) as the extension form
- Backend: each branch is stored as a `type`/`target_uuid`/`external` triple (`toggle_on_*` / `toggle_off_*`) resolved through the shared `_resolve_dest_action`; the legacy `toggle_on_dest`/`toggle_off_dest` FK columns are retained and back-filled (migration `0019`), with the dialplan generator falling back to them for un-migrated rows
- Fixed the Custom Destination dialog overflowing the page on the taller BLF form — it now caps at `90vh` with a scrollable body
- BLF Number field now flags when the number is **already in use** by an extension, ring group, IVR menu, or another BLF toggle

### CDR Tenant & Extension Ingest (call logs)
- Fixed calls saving with `tenant=NULL` (invisible in per-tenant call logs) when the tenant `-CODE` suffix lived in fields the resolver didn't scan. Tenant is now also derived from `destination_number`, the resolved `extension_number` suffix, the dialed DID (`rdnis`/`sip_req_user`/`sip_to_user`), and `<callflow><caller_profile>` routing fields when absent from `<variables>`. Removed an unsafe caller-side DID match that mis-attributed calls to the wrong tenant (e.g. an IHDT call tagged IHS)
- WebRTC legs (busy/no-answer) report only a SIP session token (e.g. `pn1tnrgv`) as destination, leaving the extension blank. The dialplan now exports `ihs_dialed_ext=<sip_username>` onto every leg so ingest records the real extension (`901-IHDT`) on answered, busy, no-answer, and voicemail calls
- Outbound calls placed with the tenant DID as caller ID (extension only present in `caller_id_name` as `NNN-CODE`) were logged as **inbound** with a blank extension. These are now classified **outbound** and the extension is recovered from `caller_id_name`

### CDR Voicemail Classification
- Busy/no-answer→voicemail calls were stuck as **Busy** and never reclassified. Root cause: `v_xml_cdr.last_arg` was `varchar(256)` but the voicemail record-stop curl is ~427 chars, so the real voicemail A-leg insert failed ("value too long") and the synthetic USER_BUSY row survived. Migration `0008`'s AlterField never applied to the FusionPBX-owned table
- Widened `last_arg` to 1024 via migration `0010` (idempotent raw SQL) and truncate `last_arg` defensively at ingest so an over-length value can never drop a whole CDR row again
- Hid the transient "Busy" flash: a busy→voicemail call briefly showed Busy before the voicemail A-leg arrived. The call-log list and status counts now suppress bare placeholder rows (`USER_BUSY` + empty `last_app`) for a 15-second grace window; genuine quick-decline busy calls still surface after the window

### Recording Control
- Outbound calls recorded unconditionally — playing the "may be recorded" tone and recording even when the extension/tenant had recording off. Outbound recording is now gated per-extension: each extension's effective record decision (`user_record`, falling back to tenant `recording_enabled`) is exported as `ihs_record`, and the outbound route records only when `ihs_record=1`. Matches the existing per-extension control on inbound

### Voicemail Routing
- Offline/unregistered, busy, and no-answer calls no longer default to voicemail. Voicemail is reached only via an explicit `forward_user_not_registered` / `forward_busy` / `forward_no_answer` destination; otherwise the call hangs up

### Backfill (existing rows)
- `backfill_cdr_tenant`: added a DID-match pass (batched per-tenant to avoid table-wide-UPDATE deadlocks against live `mod_xml_cdr` inserts)
- `backfill_cdr_direction`: retroactively fix inbound/outbound mislabeling
- `backfill_voicemail_cdrs`: repair voicemail rows clobbered by garbage synthetic A-legs

## 2026-06-09

### Affinity (Sticky Last-Agent) Routing
- Replaced the Lua-based affinity router (`affinity_route.lua`) with a pure-Python lookup that runs in the dialplan generator at request time, using the live `caller_id_number`. The Lua script and all references to it are removed.
- Fixed the underlying failure: the deployed Lua script still contained the literal `__PG_PASSWORD__` placeholder instead of the real DB password, so every sticky call failed its DB lookup and dropped the caller to a hangup
- The dialplan cache is now bypassed for sticky DIDs so each caller gets their own affinity result instead of a cached one
- `deploy/install.sh` hardened to substitute the DB password and set `freeswitch:freeswitch` ownership on FreeSWITCH scripts (retained for any future scripts)

### CDR Status Classification
- `WENT_TO_VOICEMAIL` now requires proof that voicemail actually executed (confirmed via `last_app`). Missed calls to a voicemail-enabled extension where the caller hung up before the no-answer timeout are now correctly reported as **MISSED** instead of voicemail
- `MEDIA_TIMEOUT` calls with talk time (`billsec > 0`) are now classified as **ANSWERED** instead of FAILED — fixes long answered calls that ended on RTP silence being mislabeled as failed. Any call with talk time is ANSWERED regardless of hangup cause
- Fixed a 500 error on `GET /cdr/?extension=` caused by a stale `vm_idents` reference in the status-counts aggregate

### CDR Tenant Attribution
- Fixed calls landing with no tenant (`tenant=NULL`) and being invisible in the Client API and tenant-scoped admin views. WebRTC calls arrive with an empty context and a DID (not an extension) as caller ID, so the original tenant resolution missed them
- Tenant is now recovered from `extension_number`, `destination_number`, and SIP user fields; bridged B-legs inherit the tenant of their originating A-leg
- Backfilled existing orphaned rows: 2,464 CDRs re-attributed to their tenants

### CDR Data Integrity
- Added a unique constraint on `(call_uuid, leg)` and made B-leg ingest idempotent (`update_or_create`); synthetic A-leg creation wrapped in a transaction. Eliminates duplicate CDRs from re-delivered FreeSWITCH webhooks
- Migration `0009` removed 1,982 existing duplicate rows before applying the constraint
- CDR list `direction` filter now propagates into `status_counts` so the sidebar counts match the selected direction

### Affinity Data Cleanup
- Fixed `migrate_cdrs.py` (both copies) to preserve the full SIP username (e.g. `417-GMD`) instead of stripping to plain digits; voicemail legs still extract digits only
- Added `backfill_affinity_extensions` command; corrected 3,287 affinity rows from plain extension numbers to the suffixed `sip_username` format

### Data Cleanup (one-time)
- Removed 782 bogus GMD "missed" CDRs that were artifacts of the broken-Lua window (`last_app=lua` / `affinity_route.lua` / `billsec=0` / `missed`, dated Jun 8 17:02 – Jun 9 05:30). Verified none had talk time before removal

## 2026-06-08

### Client API
- Voicemail messages: the `number` filter now matches both caller ID number and caller ID name (global search), like the `search` filter
- Voicemail messages: search/number filters are applied to the unread count too; single-mailbox responses now return both `unread` (global mailbox unread, ignores filters) and `filtered_unread` (unread within the active search/number filter)

## 2026-06-06

### Client API
- Extensions: pass `export=all` (or `export=true`) to return the full extension list without pagination; default list responses now paginate (page size 20, `?page_size=` override)

### Admin Panel
- CDR list & summary: restricted to A-leg calls so each call is counted once — fixes the admin CDR view showing roughly double the rows/counts and disagreeing with the Client API (e.g. for tenant GMD)

### Tooling
- Fixed `migrate_cdrs.py` and `migrate_voicemails.py` Django bootstrap (`ModuleNotFoundError: No module named 'config'`) — they now resolve the settings package when run from `sip2fs_migration/`

## 2026-06-05

### Client API
- CDR API: pass `export=true` to return all filtered rows without pagination
- CDR summary: now honors `status` and `direction` filters (scopes the whole summary)
- CDR summary: zero-valued fields are no longer omitted — every bucket is always returned (shows `0`)
- CDR summary: top-level `voicemail` block now reports actual mailbox messages (`total`/`read`/`unread`) from the voicemail store, independent of call filters
- CDR summary: added `incoming.failed` bucket so failed inbound calls are reported distinctly instead of folding into `missed`
- A missed inbound call to an extension whose no-answer routing is voicemail is now reported as **voicemail** (not missed) everywhere — summary buckets, per-row status, `status_counts`, and status filtering

### Admin Panel
- CDR list: per-row status reflects the same missed→voicemail reclassification as the Client API

### FreeSWITCH / Calls
- Fixed call webhook delivery logging — delivery records now save correctly (was failing on a missing `url` value)

### Tooling
- Bulk import scripts (extensions, DIDs) can now be run from any directory
- Added `backfill_cdr_tenant` management command — assigns tenant to orphaned CDR rows (written directly by FreeSWITCH) using the extension's tenant suffix, so they appear in tenant-scoped call history

## 2026-06-04

### Permissions & Access Control
- Added role-based permissions: **Super Admin**, **Admin**, **User**
- Page-level access control per user role
- Fax number access restrictions per user role
- **Auto-reconfig** — role and setting changes apply immediately; no logout/login required
- Tenant scoping for user queries (API + frontend); standard users locked to a single tenant

### Fax
- Inline fax box management and email editing on the Destinations page
- Super Admins can now delete fax boxes
- Fax box selection scoped per tenant
- Client API: filter fax files by fax box (`?fax=<fax_uuid>`); summary counts respect the filter
- Fax station ID now always populated: outbound uses the sender's caller ID, inbound uses the caller's number

### FreeSWITCH / Calls
- Added support for local IP connections within FreeSWITCH
- Fixed incoming calls not connecting — dialplan now matches registrations across all SIP profiles
- Fixed devices wrongly showing offline in the frontend
- Removed congestion metrics from Call History (IHSPhone)
