# Changelog

All notable changes to IHS-PBX are documented in this file.
Newest entries on top.

## 2026-07-21

### Security — tenant isolation leak on the FreeSWITCH live views (active calls, registrations)
A tenant admin could see **other tenants' live data** (e.g. a CGH admin seeing IHDT's active calls on the dashboard). Root cause: `_tenant_code_for_request()` in `backend/esl/views.py` granted the `?tenant=` override to any `is_staff` user (not just superusers) and returned `None` — interpreted downstream as *no filter* — whenever `request.tenant` was null. Tenant admins administer tenants via the `admin_tenants` M2M and typically have a null `tenant` FK, so their requests fell through to the unscoped path.

- **Rewrote `_tenant_code_for_request()` to fail closed.** Superusers: `?tenant=` selects any tenant, absent = all. Everyone else: the requested tenant is honored **only if** the user owns it (`user.tenant`) or administers it (`admin_tenants`); an unauthorized or ambiguous request returns a new `_TENANT_DENY` sentinel instead of `None`.
- **All 7 call sites now handle `_TENANT_DENY`** as "return nothing" (empty list / `403`), never as "no filter": `FSCallsView`, `FSRegistrationsView`, `FSExtensionStatusView`, `FSPeerHistoryView`, `FSRebootView`, `FSDeregisterView`, `FSOriginateView`.
- **Body `tenant_code` fallback** on the reboot/deregister actions is now superuser-only.

### Tenants — enable/disable option (keeps data, excludes from FreeSWITCH XML)
Disabling a tenant now retains all its data in the DB but removes it from every FreeSWITCH XML lookup — no registrations, calls, or inbound DID routing until re-enabled. Reuses the existing `Tenant.tenant_enabled` field (no migration).

- **XML exclusion** (`backend/freeswitch_config/generators.py`): new `_tenant_active()` helper; `_resolve_domain()` treats a disabled tenant's domain as non-existent (directory + dialplan return not-found), the dialplan fallback-domain picker skips disabled tenants, and the global public/DID context excludes disabled tenants' destinations.
- **Cache invalidation** (`backend/freeswitch_config/signals.py`): registered a `Tenant` post_save/post_delete handler that flushes dialplan + directory + sticky-DID caches so a toggle takes effect immediately.
- **Frontend** (`frontend/src/pages/TenantList.jsx`): a Status (Active/Disabled) toggle in the tenant create/edit form, plus an inline clickable status badge in the list for one-click enable/disable. Edit now saves via PATCH (`tenants.patch` added in `api/index.js`) so it only sends the form's fields.

### API — stop browsers caching list responses (stale-after-delete fix)
Deleting a row (e.g. an extension) left the deleted item visible in the list until a hard refresh. DRF responses carried no `Cache-Control`, so browsers applied heuristic caching to `GET` list calls.

- Added `NoCacheApiMiddleware` (`backend/core/middleware.py`, registered in `config/settings/base.py`) setting `Cache-Control: no-store` on all `/api/` responses. App-wide fix — every list page, not just Extensions.

## 2026-07-20

### pgbouncer — connection pooler in front of all Postgres databases
Installed pgbouncer to front all three PostgreSQL databases — `ihspbx`, `ihspbx_cdr`, `ihspbx_metrics` — on `127.0.0.1:6432` in **transaction** pooling mode. Django (and the ESL listener, Celery, and metrics samplers) now connect through the pooler instead of hitting Postgres `5432` directly.

- **Cutover** (`.env`): `DB_HOST` `localhost` → `127.0.0.1`, `DB_PORT` `5432` → `6432`; the CDR/metrics DB configs inherit the same host/port. Pre-cutover `.env` preserved as `.env.bak.pgbouncer`.
- **Config** (`/etc/pgbouncer/`): `pgbouncer.ini` + `userlist.txt` (both `0640 postgres:postgres`); original stock config kept as `pgbouncer.ini.orig`.
- **Gotchas worked through:**
  - **SCRAM auth**: the SCRAM verifier from `pg_authid` (and `auth_query`) fails the server-side leg — pgbouncer needs the **cleartext password in `userlist.txt`** so it can complete a fresh SCRAM handshake to the backend while still verifying the client's SCRAM handshake.
  - **`search_path` startup option**: Django sends `-c search_path=public`, which pgbouncer rejects unless `ignore_startup_parameters = extra_float_digits,search_path` is set. Also pinned at the role level (`ALTER ROLE ihspbx SET search_path=public`).
  - **Server-side cursors**: transaction pooling breaks them → `DISABLE_SERVER_SIDE_CURSORS = True` in `config/settings/base.py`.
- **Observability note:** metrics samplers read the same `.env`, so the `pg_conns=X/Y` figure now reflects the pgbouncer-side pool rather than the raw client connection count.

## 2026-06-23

### HOMER SIP capture — deployed as the capture engine (native, no Docker)
Stood up HOMER on the FreeSWITCH host to capture SIP signaling, replacing reliance on the rolling tcpdump pcaps for the CDR SIP/PCAP viewer. Key win: HEP taps inside `mod_sofia` **before encryption**, so TLS/wss (webrtc) legs are captured in cleartext — which tcpdump could not do.

- **heplify-server 1.60.3** (`/etc/heplify-server.toml`, systemd `heplify-server`): receives HEP on `127.0.0.1:9060/udp` only, writes to PostgreSQL `homer_data`. Needs the `luajit` apt dependency.
- **homer-app 1.5.14** (`/usr/local/homer/`, systemd `homer-app`): admin UI + REST API on `127.0.0.1:9080` (loopback only). Login `admin` / `sipcapture` (default — change it).
- **Reuses the existing PostgreSQL 18** instance: dedicated `homer` role + `homer_config` / `homer_data` databases. PG18 compatibility verified for both components.
- **FreeSWITCH**: enabled `capture-server = udp:127.0.0.1:9060;hep=3;capture_id=100` in `sofia.conf.xml`, plus `sip-trace`/`sip-capture` on the internal, internal-private, external, and webrtc profiles.

### CDR viewer — sources per-leg SIP from HOMER, with pcap fallback
- `backend/apps/xml_cdr/sip_capture.py`: `leg_sip_view()` now resolves each leg as **stored pcap → HOMER (by Call-ID) → tcpdump/sngrep slice**. HOMER creds read from `HOMER_*` settings (`config/settings/base.py`, `.env`). The old `sip-capture.service` stays as fallback.

### Tenant-scoped SIP search + leg-wise ladder (internal + client API)
HOMER itself is **not** tenant-aware (all tenants share one SIP domain), so tenant isolation is enforced in IHS-PBX, which knows the DID/extension→tenant map.

- **Attribution** (`backend/apps/xml_cdr/homer_tenant.py`): maps a SIP number to a tenant via the `Destination` (DID) and `Extension` tables (cached index). Unmatched numbers (scanner floods, unassigned DIDs) are an "unattributed" bucket shown only to superadmins.
- **Search** (`backend/apps/xml_cdr/homer_search.py`): queries `homer_data` by time window, groups messages into calls, attributes each to a tenant, and scopes results to the caller. Filters: `number`, `extension` (bare + tenant-suffixed forms), `call_id`; time via `from`/`to` (date **or** datetime), `date`, `date_from`/`date_to`; pagination (`page`, `page_size` default 20). Forked/bridged calls collapse to **one row per call** (`group=call`) with nested legs — CDR `bridge_uuid` correlation plus a heuristic fork-merge for legs with no CDR row; `group=leg` returns raw per-leg rows.
- **Internal API** (JWT): `GET /api/v1/cdr/homer-search/` and `GET /api/v1/cdr/homer-ladder/`. Tenant users are hard-scoped to their tenant; superadmins see all + can filter `?tenant=`. Bypass-tested (cross-tenant `?tenant=` injection and foreign Call-ID both denied).
- **Client API** (API key, single-tenant): `GET /<tenant_uuid>/sip/search/` and `/sip/ladder/` (`backend/apps/client_api/views.py`, `urls.py`). The ladder returns full leg-wise detail ("First Leg / Second Leg 0..N") like the CDR pcap view; a Call-ID must belong to the key's tenant or it 403s.

### Frontend — SIP Search tab + HOMER admin link
- **"SIP Search" tab** in the CDR page (`frontend/src/pages/SipSearchPanel.jsx`, wired into `Cdr.jsx`): filter bar (number/extension/Call-ID/date range, tenant selector for superadmins), results grid (one row per call) with expandable rows that lazy-load each leg's decoded SIP ladder. New `cdr.homerSearch` / `cdr.homerLadder` API methods.
- **Sidebar** (`frontend/src/components/Sidebar.jsx`): superadmin-only "HOMER (SIP Capture)" link under Monitoring; added `external` nav-item support (opens a new tab).

### nginx — reverse-proxy HOMER at /homer/
- `deploy/nginx.conf` (and the live site): `/homer/` → loopback `127.0.0.1:9080`, prefix-stripped, with `sub_filter` injecting `<base href="/homer/">` so HOMER's root-built Angular bundle resolves its assets/API under the subpath (done in nginx, not by editing `dist/index.html`, so it survives HOMER upgrades). Gated by HOMER's own login.

### Security / deploy
- **PostgreSQL access restricted**: `listen_addresses` and `pg_hba.conf` tightened from open (`0.0.0.0/0`) to localhost + a single trusted peer.
- `deploy/install.sh` provisions HOMER end-to-end: creates the `homer` DBs/role, installs heplify-server + homer-app, configures both, seeds the schema + default admin, and enables the services.

## 2026-06-18

### Migration — extension & DID importer pulling from the legacy OpenAPI
New standalone script `backend/sip2fs_migration/import_extensions_api.py` that bulk-imports a tenant's extensions and DIDs directly from the legacy PBX OpenAPI (instead of hand-built CSVs):

- **Extensions** are fetched from `…/openapi.php/extensions` and created/updated against the tenant. The API does not expose passwords, so each extension gets a fresh 16-char password generated with the **same scheme as the frontend** (`Extensions.jsx::generatePassword` — ≥1 upper, ≥1 lower, ≥1 digit, 13 more alphanumeric, Fisher-Yates shuffled), using `secrets` for crypto-quality randomness. Passwords are guaranteed unique within a run.
- **DIDs** are fetched from `…/openapi.php/dids` (derived from the same base) and mapped into `Destination`: E.164 built from `di_country`+`di_area`+`di_number`, name/comment, and fax settings (receive flag, station id, protocol, email, store) + CNAM. Deduped against existing `destination_number` and within the feed.
- **Ergonomics:** only `--tenant` and `--api-key` are required — the OpenAPI base is defaulted (override with `--api-base`) and `--api-tenant` defaults to `--tenant`. Supports `--dry-run`, `--update`, `--extensions-only`, `--dids-only`.

### Custom Destinations — Toggle (BLF switch) made fully working
A toggle custom destination (a DB-backed ON/OFF switch that routes inbound calls to one of two destinations and shows a phone BLF lamp) was effectively non-functional. Fixed end to end:

- **Routing now follows the toggle state.** A DID pointed at a `kind='toggle'` custom destination was resolving to the toggle's own `dest_type` (usually `hangup`), so inbound calls just answered and hung up regardless of ON/OFF. `_resolve_dest_action` now transfers a toggle target into its router (`transfer toggle_<uuid> XML default-<tenant>`), which follows the ON branch (`<action>`) / OFF branch (`<anti-action>`) — e.g. ON→ext 901, OFF→ext 909 (`backend/freeswitch_config/generators.py`)
- **Key press reaching the destination but never flipping — fixed.** The router gate (`^toggle_<uuid>$`) had `break="never"`, so a plain dialled number fell through into the state conditions, matched `^true$`, and routed to the ON destination instead of the flip handler. The gate now hard-stops (default `break=on-false`) so a dialled number falls to `toggle_blf_<uuid>` and flips the state
- **Multi-tenant dialable number.** The toggle's BLF/feature-code extension is now matched in both bare and tenant-suffixed forms (`800` and `800-IHDT`), matching how extensions/parking are dialed inside a `default-<tenant>` context

### Custom Destinations — virtual BLF lamp (green/red) via FusionPBX `flow+` proto
A bare `<ext>@domain` presence cannot light a BLF lamp for a virtual extension — FreeSWITCH renders any entity with no registration as `closed`/`Unregistered` (verified: plain presence, dialog-inject, and held-loopback all fail). Adopted the FusionPBX feature-code lamp mechanism:

- **New self-contained `deploy/freeswitch/scripts/blf_subscribe.lua`** (no FusionPBX framework dependency): binds `PRESENCE_PROBE`, and for `proto=flow` publishes the lamp from the mod_db key `call_flow_status/*<ext>-<TENANT>@<domain>` using FusionPBX `turn_lamp` headers (`confirmed`=lit, `terminated`=off). Enabled as a `startup-script` in `lua.conf.xml` (`deploy/freeswitch/lua.conf.xml`)
- **Phone BLF key Value is `flow+*<ext>-<TENANT>`** (e.g. `flow+*800-IHDT`), tenant-suffixed for multi-tenant isolation — same convention as park keys (`park+…`)
- **Lamp polarity:** ON = green (unlit), OFF = red (lit). `CustomDestination.push_toggle_state` and the dialplan `toggle_exec` keep the `call_flow_status/*…` mod_db key in sync (`backend/apps/custom_destinations/models.py`, `backend/esl/client.py` — `presence_in` now splits the proto from the `+`)
- **"Worked only once" — fixed.** A direct `PRESENCE_IN` does not generate a NOTIFY for a flow-proto subscription, so the lamp only updated on the phone's first subscribe. Both the UI/API push and the dialplan flip now fire a `PRESENCE_PROBE`, which the running `blf_subscribe.lua` answers via the same path as the initial subscribe — so the lamp updates on every change
- **"No Response" on the phone — fixed.** A Grandstream BLF key press dials its full Value (`flow+*800-IHDT`), which the dialplan didn't match; the press fell through, never answered cleanly, and the phone showed "No Response" (state still flipped). The toggle BLF extension now matches the `flow+*` form, answers, plays a clear ON/OFF confirmation tone, and hangs up with `NORMAL_CLEARING`

### Custom Destinations — toggle flips kept out of CDR, logged separately
- **Toggle flips are no longer recorded as calls.** The dialplan tags the flip leg `ihs_toggle_flip=true`; CDR ingest (`backend/freeswitch_config/views.py` `_process_cdr`) detects the tag and returns early — no `XmlCdr` row
- **New `ToggleEvent` audit log** (`backend/apps/custom_destinations/models.py`, table `v_custom_destination_toggle_events`, migration `custom_destinations 0020`) records each ON/OFF change with state, source (`blf`/`ui`/`api`), actor, and timestamp. Phone-key flips are logged during CDR ingest; UI/API flips in the `set-state` view
- **New endpoint** `GET /api/.../custom-destinations/{uuid}/toggle-events/?limit=N` returns recent flips for display on the custom destination page

### Deploy
- Staged the BLF lamp setup for future servers: `deploy/freeswitch/scripts/blf_subscribe.lua`, `deploy/freeswitch/lua.conf.xml`, and a step in `deploy/install.sh` (copy the script, enable the `startup-script` line, program phones with `flow+*<ext>-<TENANT>`)

## 2026-06-17

### CDR — per-leg SIP/PCAP capture & viewer
- **New: capture and view the SIP signaling for each call leg**, the same ladder you'd see in `sngrep`, rendered per leg ("First Leg", "Second Leg 0..N") in the CDR detail. Each leg shows the numbered frame summary (`Request: INVITE …` / `Status: 200 OK …`) and a **Download .pcap** button (openable in sngrep/Wireshark)
- **Always-on, tenant-only capture** (`deploy/sip-capture.service`): a `tcpdump` sidecar records SIP-only (no RTP) on all SIP-bound interfaces, packet-buffered (`-U`) into 5-minute rotating files in `/var/spool/sip/`. The BPF filter is **auto-derived from FreeSWITCH's configured gateways** (`deploy/gen-sip-capture-filter.sh`, regenerated on each service start): all authenticated internal/webrtc legs plus external `:5060` traffic only to/from our carrier gateways — dropping the open-internet scanner flood (cut capture volume drastically)
- **Per-call slicing runs entirely off the ingest path.** A Celery Beat sweep (every minute, tenant calls only) slices each call's dialog out of the rolling capture **once** and stores the (tiny, ~5KB) SIP-only pcap **in the CDR row** (`sip_pcap_data`). The viewer decodes straight from the DB — no disk dependency, no per-open scan (open went from ~8–17s live-scan to ~10ms). CDR ingest does **no** pcap work, so new calls still appear in the list instantly
  - Capture/slice: `backend/apps/xml_cdr/sip_capture.py`, `backend/apps/xml_cdr/tasks.py` (`slice_call_pcap`, `sweep_unsliced_pcaps`)
  - API: `GET /api/v1/cdr/{uuid}/pcap/` (per-leg frame summary), `GET /api/v1/cdr/{uuid}/pcap/{leg}/download/` (raw .pcap)
  - Decode is port-independent (reads the SIP start-line from the payload), so internal `:5080`/webrtc `:5066` legs render too — not just `:5060`
  - sngrep 1.6.0 accepts only one `-I` input, so calls spanning a rotation boundary are sliced per-file and concatenated; a slice with no packets stays retryable until the call ages past the capture window, then is marked so the sweep skips it
- **CDR detail now has three tabs: Legs · Details · SIP/PCAP** (`frontend/src/pages/Cdr.jsx`). "Details" surfaces the full call-flow timeline + per-leg technical fields + bridge summary

### CDR — moved to its own database
- **Call detail records now live in a separate `ihspbx_cdr` Postgres database** so they can be backed up / retained on their own schedule and so CDR volume doesn't contend with the app DB. Routed via a new `CdrRouter` (`backend/freeswitch_config/routers.py`); connection configured in `backend/config/settings/base.py` (override with `CDR_DB_*` in `.env`)
- **Decoupled CDRs from the `tenant`/`domain` FKs** (those can't span databases). Added denormalized `tenant_uuid_val` / `tenant_code` / `domain_uuid_val` / `domain_name` columns on the CDR row (migration `0012`, backfilled), made the FKs `db_constraint=False`, and switched all reads + tenant-scoping to the denormalized columns — no cross-DB join anywhere. Ingest writes the denormalized values on every CDR
- Migrations: `xml_cdr 0011`–`0015` (sip_call_id, denormalize tenant/domain, fk no-constraint, sip_pcap_path, sip_pcap_data)
- The old `v_xml_cdr` table in the main DB was migrated and renamed `v_xml_cdr_migrated_20260617` (kept as a safety net; drop after verification)

## 2026-06-16

### Fax — Cancel & Delete
- Added the ability to **cancel a pending fax**. Cancel tears down the in-flight FreeSWITCH channel (`uuid_kill … ORIGINATOR_CANCEL`) and marks the record `failed`, which also makes `poll_fax_result` bail on its next run. **Pending-only**: cancelling a fax that has already reached a terminal status (`sent`/`received`/`failed`) returns `400` with a clear message
- **React admin (Fax page):** a Cancel button now appears in each fax row **only while status is `pending`**, with a confirm prompt, in-progress spinner, and success/error toast
  - `POST /api/v1/fax/files/{fax_file_uuid}/cancel/` (new action on `FaxFileViewSet`)
- **Client API:** added cancel + delete for external integrators
  - `POST   /api/v1/client/{tenant_uuid}/fax/files/{fax_file_uuid}/cancel/` — cancel (pending only)
  - `DELETE /api/v1/client/{tenant_uuid}/fax/files/{fax_file_uuid}/` — delete the record and its on-disk file (cancels first if still pending, so a live send is never orphaned)
- **Fixed client API fax DELETE silently failing.** Requests sent without a trailing slash hit Django's `APPEND_SLASH` and received a `301` redirect; a 301 on DELETE/POST drops the method, so the request never executed (the slash form returned `204` and worked). The fax-file detail and cancel routes are now **slash-optional** (matched via `re_path`) so both forms reach the view directly with no redirect
- **DELETE response** changed from an empty `204 No Content` to `200 OK` with `{"status": "deleted"}` so clients that parse the response body get a confirmation

### Ops — runaway fax poll storm stopped
- A fax (`5a0e5dfc…`) was stuck `pending` and `poll_fax_result` retried it **422k+ times**, saturating the Celery `default` queue and starving webhook delivery — IHDT `did.updated` webhooks were left in `pending`/`code None`. Cancelling the fax (marking it `failed`) made the poll task bail and freed the queue. The self-amplifying retry path in `poll_fax_result` is flagged as a follow-up code fix

## 2026-06-15

### CDR — "No Answer" vs "Failed"
- Outbound calls that end with `NORMAL_CLEARING` and `billsec=0` (a ring-no-answer where FreeSWITCH tore down the A-leg after the bridge originate timed out) now classify as **No Answer** instead of the generic **Failed**. `backend/apps/client_api/serializers.py`

### WebRTC outbound — fixed "connecting, no audio, then drops"
- Removed `bridge_codec_string=PCMU` from the generated outbound route. It forced PCMU onto the **WebRTC (browser) leg**, which offers opus — breaking media negotiation so the caller heard silence and cancelled (`ORIGINATOR_CANCEL`). The browser A-leg now keeps its own codec and FreeSWITCH transcodes to PCMU toward the gateway; `nolocal:absolute_codec_string=PCMU` still gives the Bandwidth gateway the PCMU it requires. `backend/freeswitch_config/generators.py`

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
