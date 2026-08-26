"""Tenant-scoped search over HOMER-captured SIP.

Queries the shared homer_data store for INVITE dialogs in a time window,
groups messages into calls by Call-ID, attributes each call to a tenant via
the DID/extension index (see homer_tenant), and returns only the calls the
caller is allowed to see:

  - superadmin: all calls, optionally filtered to one tenant_id; also sees the
    'unattributed' bucket (scanner floods / unassigned DIDs).
  - tenant user: only calls attributed to their tenant. Never sees
    unattributed traffic.

This is the backend the Cloud PBX React "SIP / PCAP" search talks to. HOMER stays
the capture engine; tenant isolation is enforced here, where the DID↔tenant
map and per-user scoping live.
"""
import psycopg2

from .sip_capture import _homer_settings, _homer_partitions
from .homer_tenant import build_index, attribute


def _connect(cfg):
    return psycopg2.connect(
        host=cfg['host'], port=cfg['port'], dbname=cfg['name'],
        user=cfg['user'], password=cfg['password'], connect_timeout=3,
    )


def _existing_call_partitions(cur, window_start, window_end):
    """Return the hep_proto_1_call_* partitions that exist for the window."""
    candidates = [t for t in _homer_partitions(window_start, window_end)
                  if '_call_' in t]
    if not candidates:
        return []
    cur.execute(
        "select table_name from information_schema.tables "
        "where table_schema='public' and table_name = any(%s)",
        (candidates,),
    )
    return [r[0] for r in cur.fetchall()]


def search_calls(window_start, window_end, *, tenant_id=None, is_superadmin=False,
                 number='', call_id='', extension='', group='call', limit=200):
    """Search captured SIP calls in [window_start, window_end].

    tenant_id        — restrict to this tenant (required for non-superadmin).
    is_superadmin    — if True, may see all tenants + unattributed; tenant_id, when
                       given, narrows to that tenant.
    number / call_id — optional filters (substring match on number; exact-ish callid).
    extension        — optional: match calls involving a specific extension. Matches
                       the bare number (101) AND the tenant-suffixed SIP form
                       (101-DMD) on from_user / to_user / ruri_user. Precise, unlike
                       `number`'s substring match.
    Returns a list of call dicts ordered newest-first:
      {call_id, start_time, from_user, to_user, tenant_id, direction, msg_count, methods}
    """
    cfg = _homer_settings()
    if not cfg['enabled']:
        return []
    # A non-superadmin with no tenant can see nothing.
    if not is_superadmin and not tenant_id:
        return []

    index = build_index()
    conn = None
    calls = {}
    try:
        conn = _connect(cfg)
        with conn.cursor() as cur:
            tables = _existing_call_partitions(cur, window_start, window_end)
            if not tables:
                return []
            where = ["data_header->>'method' = 'INVITE'"]
            params = []
            if call_id:
                where.append("data_header->>'callid' = %s")
                params.append(call_id)
            if number:
                where.append("(data_header->>'from_user' like %s "
                             "or data_header->>'to_user' like %s "
                             "or data_header->>'ruri_user' like %s)")
                like = f'%{number}%'
                params.extend([like, like, like])
            if extension:
                # Exact match on the bare extension and its tenant-suffixed SIP
                # form(s) (e.g. 101 and 101-DMD). Derive the suffixed forms from
                # the index so we don't guess the tenant code.
                ext_forms = {str(extension)}
                for key in index:
                    # index keys include sip_usernames like '101-DMD'
                    if key.split('-', 1)[0] == str(extension):
                        ext_forms.add(key)
                forms = list(ext_forms)
                where.append("(data_header->>'from_user' = any(%s) "
                             "or data_header->>'to_user' = any(%s) "
                             "or data_header->>'ruri_user' = any(%s))")
                params.extend([forms, forms, forms])
            # Tenant pre-filter in SQL: when scoped to a tenant, restrict to that
            # tenant's own numbers (DIDs + extensions) so the row cap isn't consumed
            # by the scanner flood before the tenant's real calls are reached. Match
            # from_user OR to_user OR ruri_user against the tenant's number set.
            if tenant_id:
                tenant_numbers = [n for n, t in index.items() if t == tenant_id]
                if not tenant_numbers:
                    return []
                # Match on the last-10-digit form for DIDs and exact for extensions.
                # Build an IN list against both raw and a regexp_replace'd 10-digit key.
                where.append(
                    "(data_header->>'from_user' = any(%s) "
                    "or data_header->>'to_user' = any(%s) "
                    "or data_header->>'ruri_user' = any(%s) "
                    "or right(regexp_replace(data_header->>'from_user','\\D','','g'),10) = any(%s) "
                    "or right(regexp_replace(data_header->>'to_user','\\D','','g'),10) = any(%s) "
                    "or right(regexp_replace(data_header->>'ruri_user','\\D','','g'),10) = any(%s))"
                )
                # Exact keys (extensions/sip_usernames) and 10-digit keys (DIDs).
                exact_keys = tenant_numbers
                tendigit_keys = [n for n in tenant_numbers if n.isdigit() and len(n) == 10]
                params.extend([exact_keys, exact_keys, exact_keys,
                               tendigit_keys, tendigit_keys, tendigit_keys])
            clause = ' and '.join(where)
            union = ' union all '.join(
                f"select create_date, data_header, protocol_header "
                f'from public."{t}" where {clause}'
                for t in tables
            )
            cur.execute(union + ' order by create_date desc limit %s',
                        tuple(params * len(tables)) + (limit * 4,))
            for create_date, dh, ph in cur.fetchall():
                dh = dh or {}
                cid = dh.get('callid')
                if not cid:
                    continue
                existing = calls.get(cid)
                if existing is not None:
                    # Track the EARLIEST packet as the leg's start_time (rows arrive
                    # newest-first, so a later row is an earlier packet).
                    if create_date.isoformat() < existing['start_time']:
                        existing['start_time'] = create_date.isoformat()
                    continue
                frm = dh.get('from_user') or ''
                to = dh.get('to_user') or ''
                ruri = dh.get('ruri_user') or ''
                owner = attribute([to, ruri, frm], index=index)
                calls[cid] = {
                    'call_id': cid,
                    'start_time': create_date.isoformat(),
                    'from_user': frm,
                    'to_user': to,
                    'tenant_id': owner,
                    'src_ip': (ph or {}).get('srcIp', ''),
                    'dst_ip': (ph or {}).get('dstIp', ''),
                }
    except Exception:  # noqa: BLE001 — search is read-only/best-effort
        return []
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:  # noqa: BLE001
                pass

    # ── Tenant scoping ────────────────────────────────────────────────────
    results = []
    for c in calls.values():
        if is_superadmin:
            if tenant_id and c['tenant_id'] != tenant_id:
                continue
            results.append(c)
        else:
            # Tenant user: only their own attributed calls; never unattributed.
            if c['tenant_id'] == tenant_id:
                results.append(c)
    results.sort(key=lambda x: x['start_time'], reverse=True)

    if group == 'call':
        results = _group_by_call(results)

    return results[:limit]


def _group_by_call(leg_rows):
    """Collapse per-Call-ID leg rows into one row per logical call.

    HOMER has no native call correlation, so we group via the CDR: each leg's
    SIP Call-ID maps to an XmlCdr row, whose call_uuid/bridge_uuid identifies the
    logical call (the A-leg's call_uuid; B-legs carry bridge_uuid = that uuid).
    All legs sharing that key collapse into one row with nested `legs`. Legs with
    no CDR match (e.g. scanner noise) stay standalone. The grouped row adopts the
    earliest (A-leg-ish) from/to so forked rings show as a single call.
    """
    from .models import XmlCdr  # noqa: PLC0415

    call_ids = [r['call_id'] for r in leg_rows]
    if not call_ids:
        return leg_rows

    # Map sip_call_id -> (call_uuid, bridge_uuid, leg) for the legs we found.
    cdr_map = {}
    for row in XmlCdr.objects.filter(sip_call_id__in=call_ids).values(
        'sip_call_id', 'call_uuid', 'bridge_uuid', 'leg'
    ):
        cdr_map.setdefault(row['sip_call_id'], row)  # first wins

    def _group_key(leg):
        cdr = cdr_map.get(leg['call_id'])
        if not cdr:
            return ('cid', leg['call_id'])               # ungrouped: itself
        # A-leg → its own call_uuid; B-leg → the call_uuid it bridged from.
        key = cdr.get('bridge_uuid') or cdr.get('call_uuid')
        return ('call', str(key)) if key else ('cid', leg['call_id'])

    grouped = {}
    order = []
    for leg in leg_rows:
        key = _group_key(leg)
        if key not in grouped:
            grouped[key] = {
                **{k: leg[k] for k in ('call_id', 'start_time', 'from_user',
                                       'to_user', 'tenant_id')},
                'legs': [],
            }
            order.append(key)
        g = grouped[key]
        g['legs'].append({
            'call_id': leg['call_id'],
            'start_time': leg['start_time'],
            'src_ip': leg.get('src_ip', ''),
            'dst_ip': leg.get('dst_ip', ''),
            'from_user': leg['from_user'],
            'to_user': leg['to_user'],
        })
        # Keep the earliest leg's start_time / identity as the call's headline.
        if leg['start_time'] < g['start_time']:
            g['start_time'] = leg['start_time']
            g['from_user'] = leg['from_user']
            g['to_user'] = leg['to_user']
            g['call_id'] = leg['call_id']

    out = [grouped[k] for k in order]

    # ── Second pass: heuristic fork-merge ────────────────────────────────────
    # CDR grouping misses forks whose unanswered leg never produced a CDR row
    # (the device that rang but didn't answer). Such forks share the same
    # tenant + from_user + to_user and start within a few seconds of each other
    # (the PBX forks all registered contacts at once). Merge those into one call.
    from datetime import datetime as _dt  # noqa: PLC0415
    FORK_WINDOW_SEC = 5

    def _ts(s):
        try:
            return _dt.fromisoformat(s)
        except ValueError:
            return None

    out.sort(key=lambda x: x['start_time'])  # earliest first for merge
    merged = []
    for g in out:
        gt = _ts(g['start_time'])
        host = None
        for m in merged:
            if (m['tenant_id'] == g['tenant_id']
                    and m['from_user'] == g['from_user']
                    and m['to_user'] == g['to_user']):
                mt = _ts(m['start_time'])
                if gt and mt and abs((gt - mt).total_seconds()) <= FORK_WINDOW_SEC:
                    host = m
                    break
        if host is not None:
            host['legs'].extend(g['legs'])
        else:
            merged.append(g)

    for g in merged:
        # de-dup legs by call_id (a leg can appear once)
        seen = set()
        uniq = []
        for l in g['legs']:
            if l['call_id'] in seen:
                continue
            seen.add(l['call_id'])
            uniq.append(l)
        g['legs'] = uniq
        g['leg_count'] = len(uniq)

    merged.sort(key=lambda x: x['start_time'], reverse=True)
    return merged
