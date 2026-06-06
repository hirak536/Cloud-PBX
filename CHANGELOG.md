# Changelog

All notable changes to IHS-PBX are documented in this file.
Newest entries on top.

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
