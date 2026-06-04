# Changelog

All notable changes to IHS-PBX are documented in this file.
Newest entries on top.

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
