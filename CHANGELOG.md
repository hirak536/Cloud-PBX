# Changelog

All notable changes to IHS-PBX are documented in this file.
Newest entries on top.

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
