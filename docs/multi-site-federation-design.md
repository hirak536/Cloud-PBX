# Multi-Site Federation Design — Houston + Dallas Unified PBX Portals

**Status:** Draft for review · **Date:** 2026-07-20 · **Author:** infra/eng

## 1. Goal

Two independent PBX servers — **Houston** (this box, `23.189.208.80`) and
**Dallas** (new) — each running its own FreeSWITCH + Django portal on its own
domain, each handling its own live calls. Requirement:

> A user logging into **either** portal must see **everything** — voicemail,
> call recordings, CDRs, and faxes — from **both** sites.

Inter-site latency is **~6 ms RTT**.

## 2. Key decision: federate the *view*, don't share the *database*

Sharing one read-write database across both sites is rejected:

- **Latency:** live call routing / XML-CURL / portal pages issue many small
  sequential queries. At 6 ms RTT each, running them across the link adds
  100–300 ms+ per request — user-visible, sometimes call-breaking.
- **Multi-primary conflicts:** Postgres has no native multi-master. Two sites
  writing the "same" DB needs BDR/pgEdge-class conflict resolution — heavy ops,
  split-brain risk.

Instead: **each site owns and writes only its own data at full local speed.**
The other site only ever *reads* it. This removes conflict risk entirely and
keeps live calls fast. Two layers:

- **Layer 1 — Metadata** (CDR/voicemail/fax rows): bidirectional **logical
  replication** into per-origin schemas; portal shows a union.
- **Layer 2 — Media files** (audio/tiff/pdf): **fetch-on-demand over HTTPS**
  from the owning site.

```
   HOUSTON (23.189.208.80)                    DALLAS (new)
   ┌───────────────────────────────┐         ┌───────────────────────────────┐
   │ FreeSWITCH  (writes local)     │         │ FreeSWITCH  (writes local)     │
   │ Django portal (hou domain)     │         │ Django portal (dal domain)     │
   │ Postgres                       │         │ Postgres                       │
   │   public   (HOU owns, RW)      │◀──────▶ │   public   (DAL owns, RW)      │
   │   dallas   (RO replica of DAL) │ logical │   houston  (RO replica of HOU) │
   │ /media/<id> endpoint           │  repl   │ /media/<id> endpoint           │
   │ /var/lib/freeswitch/... files  │         │ /var/lib/freeswitch/... files  │
   └───────────────────────────────┘         └───────────────────────────────┘
              ▲   fetch-on-demand media (HTTPS, ~6ms)  ▲
              └─────────────────────────────────────────┘
```

## 3. Layer 1 — Metadata replication

### Tables in scope
Confirmed schema facts (from current models):

| Data | Model / table | PK | Notes |
|---|---|---|---|
| CDR | `xml_cdr` (in `cdr` DB) | uuid | already a separate DB (`cloudpbx_cdr`) |
| Call recording | `recordings.CallRecording` | `call_recording_uuid` (UUID) | metadata only; file on disk |
| Media/greeting recording | `recordings.Recording` | `recording_uuid` (UUID) | " |
| Fax | `fax.Fax` / `fax.FaxFile` | UUID | `fax_file_path` → disk |
| Voicemail box | `voicemails.Voicemail` | `voicemail_uuid` (UUID) | config |
| **Voicemail message** | `voicemails.VoicemailMessage` | **`uuid` = CharField** | **lives in FreeSWITCH SQLite, not PG** (see §6) |

Almost all PKs are `uuid4` → safe to union across sites with no collision.

### Mechanism
1. Set `wal_level = logical` on both boxes (currently `replica`) — **requires one
   Postgres restart per box.**
2. On each box, `CREATE PUBLICATION` for the in-scope tables of its **own**
   `public` schema.
3. On the peer box, `CREATE SUBSCRIPTION` that writes the incoming rows into a
   dedicated schema named for the origin (`houston` on Dallas, `dallas` on
   Houston). These schemas are **read-only to the app** — only the replication
   worker writes them.

   *broken*. Local data is always current.
4. Replication is **async**: a link outage makes the peer's data *stale*, never
Because each site writes only its own `public` and the peer's rows live in a
separate schema, **there is never a write conflict and never a PK clash.**

### Portal read path
Each federated list view becomes: `local public rows` **UNION ALL**
`peer-origin schema rows`, each tagged with a `site` marker (`HOU`/`DAL`). The
`site` tag drives media-fetch URL construction (§4). Django implementation:
either DB views (`CREATE VIEW cdr_all AS SELECT ..., 'HOU' site FROM public.cdr
UNION ALL SELECT ..., 'DAL' FROM dallas.cdr`) mapped to an unmanaged model, or
two querysets merged in the app. DB view is preferred (pushes UNION to PG).

## 4. Layer 2 — Media files (fetch-on-demand)

Files are **not** in the DB — the rows store `file_path` / `fax_file_path`
`CharField`s pointing at local `/var/lib/freeswitch/...`. Current volumes:
recordings **9.8 G**, voicemail storage **2.3 G**, plus fax — growing. We do
**not** mirror these across the link.

Design:
- Each box exposes an **authenticated media endpoint**, e.g.
  `GET /api/media/<type>/<uuid>` → streams the local file for that row.
- The portal knows each row's origin site (§3 `site` tag). For a local row it
  reads disk directly; for a peer row it issues an authenticated HTTPS request
  to the peer's media endpoint and streams/downloads to the user.
- **Optional local cache** (LRU on disk) for repeat plays of remote media.
- Auth between sites: short-lived signed URL or shared service token over HTTPS
  (443, already open). The 6 ms + transfer cost is paid only on first access of
  a remote file — fine for a human clicking "play", unlike call routing.

## 5. Identity — "same users on both sites"

**This is the biggest open item and a hazard.** The requirement is that one
login works on either portal. Facts:

- `core.User` PK is `user_uuid` (UUID) — good.
- **`User.username` is NOT unique** (Django system check `auth.W004`). If both
  sites are seeded independently, the same person can end up with two different
  `user_uuid`s, or two people can share a username. Cross-site identity then
  breaks.

Options (to decide):
1. **Single source of truth for identity:** one site (or an external auth
   service) owns `User`/`Tenant`/`Domain`; the other replicates them read-only
   (same logical-replication mechanism, one-way). Logins validate against the
   authoritative copy. **Recommended** — guarantees one identity everywhere.
2. **Replicate identity bidirectionally with strict discipline:** enforce unique
   usernames and coordinate `user_uuid`s. Fragile given W004; not recommended
   without first making `username` unique.

Either way, **`Tenant` and `Domain` must be visible on both sites** (they're FK
targets for every VM/CDR/fax row), so identity + tenancy tables join the
replication set.

## 6. Known edge cases / risks

- **VoicemailMessage lives in FreeSWITCH's SQLite**, keyed by `uuid` CharField +
  `username`/`domain` strings — it is **not** in Postgres, so PG logical
  replication does not cover it. Cross-site voicemail *message* visibility needs
  a separate path: either (a) ingest VM messages into a PG table first (there is
  already `VoicemailReadState`/`VoicemailTranscript` in PG to build on), or (b)
  fetch VM message lists from the peer via API. **Decide during build.**
- **`insert_user`/`update_user`** are bare UUIDs — resolve correctly only if the
  identity set (§5) is shared.
- **Domain uniqueness:** Houston and Dallas use different SIP domains — good,
  keeps `domain`-scoped rows naturally partitioned.
- **Async lag:** a just-recorded call may take a moment to appear in the peer
  portal. Acceptable for this use case; call it out to users if needed.
- **Schema migrations:** any migration touching a replicated table must be
  applied compatibly on both sites — replication breaks on column mismatch.
  Establish a "migrate both, same version" release discipline.
- **pgbouncer:** replication connections must bypass pgbouncer (use direct
  5432, as the backup script already does). App traffic keeps using pgbouncer.

## 7. Prerequisites

- Network: PG 5432 reachable peer-to-peer over the private link (Houston already
  listens on ens19 `172.31.104.132` and `pg_hba` allows `172.31.104.0/24`; add
  the Dallas peer IP/subnet symmetrically). Media endpoint on 443 both ways.
- `wal_level = logical` on both (one restart each).
- UUID PKs — already in place for all PG-side tables in scope.
- Shared identity model chosen (§5).

## 8. Proposed rollout (phased, reversible)

1. **Identity first (§5):** pick the model; get `Tenant`/`Domain`/`User`
   replicating (one-way from the authoritative site). Prove one login sees both
   tenancies. *Nothing else works until identity is coherent.*
2. **CDR federation:** publish/subscribe `cdr`; build the `cdr_all` union view;
   surface a site-tagged CDR list in the portal. Lowest risk (append-only,
   UUID-keyed, no media).
3. **Recordings + media endpoint:** add the `/api/media/...` endpoint on both;
   federate `CallRecording`; wire portal playback to fetch remote-origin files.
4. **Fax:** federate `Fax`/`FaxFile`; reuse the media endpoint for tiff/pdf.
5. **Voicemail:** resolve the SQLite gap (§6) — likely ingest VM messages into
   PG — then federate + media-fetch.
6. **Harden:** local media cache, replication monitoring/alerting, "migrate both
   at once" release process, failover behavior when the peer/link is down.

## 9. Explicitly out of scope

- Multi-primary write to one shared DB.
- Bulk file mirroring / shared network storage for media.
- Any change to how each site handles its **own** live calls (unchanged, local).
