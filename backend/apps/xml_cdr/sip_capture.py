"""
Per-leg SIP capture slicing.

A systemd service (sip-capture.service) runs tcpdump continuously, writing
hourly SIP-only pcap files to SIP_CAPTURE_DIR. This module slices a single SIP
dialog (one Call-ID) out of those files for one CDR leg, and renders it as the
tshark-style numbered frame summary shown in the CDR UI.

Pipeline per leg:
  1. Pick the capture file(s) whose [mtime-window] overlaps the leg's call window.
  2. sngrep -I <files> <Call-ID match> -O <tmp.pcap>  → a per-leg pcap.
  3. tcpdump -nn -tttt -r <tmp.pcap>  → parsed into frame rows for the UI.

Tooling: sngrep (already installed) for the Call-ID filter + pcap export, and
tcpdump (already installed) for the SIP method/status decode. No tshark needed.
"""
import os
import re
import glob
import shlex
import subprocess
import tempfile
from datetime import timedelta

# Where sip-capture.service writes rolling pcap files (see deploy/sip-capture).
SIP_CAPTURE_DIR = os.environ.get('SIP_CAPTURE_DIR', '/var/spool/sip')

# HOMER (heplify-server) capture source. When enabled, per-leg SIP is sourced
# from the homer_data PostgreSQL partitions by Call-ID — this captures TLS/wss
# legs in cleartext (HEP taps inside mod_sofia, pre-encryption), which the
# pcap path cannot. Falls back to the pcap slice when HOMER returns nothing.
def _homer_settings():
    from django.conf import settings  # noqa: PLC0415
    return {
        'enabled': getattr(settings, 'HOMER_ENABLED', False),
        'host': getattr(settings, 'HOMER_DB_HOST', '127.0.0.1'),
        'port': int(getattr(settings, 'HOMER_DB_PORT', 5432)),
        'name': getattr(settings, 'HOMER_DB_NAME', 'homer_data'),
        'user': getattr(settings, 'HOMER_DB_USER', 'homer'),
        'password': getattr(settings, 'HOMER_DB_PASSWORD', ''),
    }


# heplify partitions SIP into hourly tables per type: hep_proto_1_<type>_<YYYYMMDD_HH00>.
_HOMER_SIP_TYPES = ('call', 'registration', 'default')

# Capture files are named sip-YYYYmmdd-HHMMSS.pcap, rotated hourly. A call can
# straddle a rotation boundary, so we widen the file-selection window on both
# ends by this margin before matching against a file's [start, start+rotate).
ROTATE_SECONDS = 300
WINDOW_MARGIN = timedelta(seconds=120)

_FNAME_RE = re.compile(r'sip-(\d{8})-(\d{6})\.pcap$')

# tcpdump SIP line, e.g.:
#  12:00:01.000000 IP 67.231.4.88.5060 > 23.189.208.20.5060: SIP, length: 950: INVITE sip:...
_TCPDUMP_RE = re.compile(
    r'^(?P<ts>\d{2}:\d{2}:\d{2}\.\d+)\s+IP6?\s+'
    r'(?P<src>[0-9a-fA-F:.]+?)\.(?P<sport>\d+)\s+>\s+'
    r'(?P<dst>[0-9a-fA-F:.]+?)\.(?P<dport>\d+):\s+'
    r'(?:UDP|tcp|TCP)?,?\s*SIP,?.*?length:?\s*(?P<len>\d+):?\s*(?P<sip>.*)$'
)


class CaptureUnavailable(Exception):
    """Raised when the capture toolchain or files are not present."""


def _parse_capture_files(window_start, window_end):
    """Return capture file paths whose coverage overlaps [window_start, window_end]."""
    if not os.path.isdir(SIP_CAPTURE_DIR):
        return []
    from django.utils.dateparse import parse_datetime  # noqa: PLC0415
    from django.utils import timezone as _tz  # noqa: PLC0415
    from datetime import timezone as _dttz  # noqa: PLC0415

    lo = window_start - WINDOW_MARGIN if window_start else None
    hi = window_end + WINDOW_MARGIN if window_end else None

    # Parse every capture file's start time first. A file's coverage END is the
    # NEXT file's start (not start+ROTATE_SECONDS): that's robust to mixed file
    # sizes — e.g. during a rotation-interval change old big files span far more
    # than the configured interval. Only the newest (still-being-written) file
    # falls back to start+ROTATE_SECONDS.
    starts = []
    for path in sorted(glob.glob(os.path.join(SIP_CAPTURE_DIR, 'sip-*.pcap'))):
        m = _FNAME_RE.search(os.path.basename(path))
        if not m:
            continue
        d, t = m.groups()
        fs = parse_datetime(f'{d[0:4]}-{d[4:6]}-{d[6:8]}T{t[0:2]}:{t[2:4]}:{t[4:6]}')
        if fs is None:
            continue
        # CDR stamps are tz-aware (UTC). tcpdump names files in the server's local
        # time; the box runs UTC, so attach UTC to keep the comparison valid.
        if fs.tzinfo is None and _tz.is_aware(window_start or window_end or fs):
            fs = fs.replace(tzinfo=_dttz.utc)
        starts.append((fs, path))

    starts.sort()
    out = []
    for i, (file_start, path) in enumerate(starts):
        if i + 1 < len(starts):
            file_end = starts[i + 1][0]            # next file's start = this file's end
        else:
            file_end = file_start + timedelta(seconds=ROTATE_SECONDS)  # newest, open file
        # Overlap test: file covers any part of the call window.
        if lo and file_end < lo:
            continue
        if hi and file_start > hi:
            continue
        out.append(path)
    return out


def slice_leg_pcap(call_id, window_start, window_end, out_path):
    """Slice all SIP packets for `call_id` from the rolling capture into out_path.

    Returns out_path on success, or None if no packets matched / no files found.
    """
    if not call_id:
        return None
    sngrep = _which('sngrep')
    if not sngrep:
        raise CaptureUnavailable('sngrep is not installed')

    files = _parse_capture_files(window_start, window_end)
    if not files:
        return None

    # IMPORTANT: sngrep 1.6.0 accepts only ONE -I input file — passing multiple
    # silently produces no output. A call can span >1 capture file (it straddles a
    # rotation boundary), so slice each file SEPARATELY (single -I, which works),
    # then concatenate the small per-file matches into out_path with tcpdump.
    # -N -q: headless, no TUI, no stdout dialog list. Match expr matches Call-ID.
    partials = []
    try:
        for idx, f in enumerate(files):
            part = f'{out_path}.part{idx}'
            cmd = [sngrep, '-N', '-q', '-O', part, '-I', f, call_id]
            try:
                subprocess.run(cmd, capture_output=True, timeout=60, check=False)
            except subprocess.TimeoutExpired:
                continue
            if os.path.exists(part) and os.path.getsize(part) > 24:
                partials.append(part)

        if not partials:
            return None
        if len(partials) == 1:
            os.replace(partials[0], out_path)
            return out_path

        # Multiple per-file matches (call straddled a rotation boundary). Merge by
        # concatenating raw pcap records: keep the first file whole (24-byte global
        # header + records), then append only the records of the rest. Dependency-
        # free and correct for same-linktype files (all ours are LINUX_SLL2).
        _concat_pcaps(partials, out_path)
        if os.path.exists(out_path) and os.path.getsize(out_path) > 24:
            return out_path
        return None
    finally:
        for p in partials:
            try:
                if os.path.exists(p):
                    os.unlink(p)
            except OSError:
                pass


def decode_frames(pcap_path):
    """Render a per-leg pcap into tshark-style frame rows for the UI.

    Returns a list of dicts: {n, time, src, dst, proto, length, info}. `time` is
    relative seconds from the first frame, matching the mockup's 0.000000 origin.
    """
    tcpdump = _which('tcpdump')
    if not tcpdump:
        raise CaptureUnavailable('tcpdump is not installed')
    # Use -A (print payload ASCII) and parse the SIP start-line out of the packet
    # body ourselves. We can't rely on tcpdump's built-in SIP dissector: it only
    # recognises SIP on its default port (5060), so internal-profile legs on 5080
    # and webrtc on 5066 print as plain "UDP, length N" with no decode. Reading
    # the payload makes decoding port-independent.
    try:
        proc = subprocess.run(
            [tcpdump, '-nn', '-tt', '-A', '-r', pcap_path],
            capture_output=True, text=True, timeout=30, check=False,
        )
    except subprocess.TimeoutExpired:
        return []

    # tcpdump -A output is: a header line per packet, followed by payload lines.
    # Header: "<epoch> [<iface> <dir> ]IP <src>.<sport> > <dst>.<dport>: ..."
    hdr_re = re.compile(
        r'^(?P<epoch>\d+\.\d+)\s+'
        r'(?:\S+\s+(?:In|Out|P)\s+)?'
        r'IP6?\s+'
        r'(?P<src>[0-9a-fA-F:.]+?)\.(?P<sport>\d+)\s+>\s+'
        r'(?P<dst>[0-9a-fA-F:.]+?)\.(?P<dport>\d+):\s'
    )

    rows = []
    base_ts = None
    cur = None  # packet being assembled

    def flush(pkt):
        nonlocal base_ts
        if not pkt or not pkt.get('startline'):
            return
        epoch = pkt['epoch']
        if base_ts is None:
            base_ts = epoch
        rows.append({
            'n': len(rows) + 1,
            'time': round(epoch - base_ts, 6),
            'src': pkt['src'], 'dst': pkt['dst'], 'proto': 'SIP',
            'length': pkt.get('length'),
            'info': _summarize_sip(pkt['startline']),
        })

    for line in proc.stdout.splitlines():
        hm = hdr_re.match(line)
        if hm:
            flush(cur)
            # Capture UDP/TCP payload length if tcpdump reported it on the header.
            lm = re.search(r'length:?\s*(\d+)', line)
            cur = {
                'epoch': float(hm.group('epoch')),
                'src': hm.group('src'), 'dst': hm.group('dst'),
                'length': int(lm.group(1)) if lm else None,
                'startline': None,
            }
            continue
        if cur is None or cur['startline'] is not None:
            continue
        # First payload line carrying a SIP start-line. tcpdump prefixes the very
        # first payload line with binary header bytes (rendered as dots); strip up
        # to the SIP token. Match either a request (METHOD sip:/tel:) or a status
        # (SIP/2.0 NNN ...).
        sm = re.search(
            r'((?:INVITE|ACK|BYE|CANCEL|REGISTER|OPTIONS|INFO|PRACK|UPDATE|'
            r'SUBSCRIBE|NOTIFY|MESSAGE|REFER|PUBLISH)\s+\S+\s+SIP/2\.0'
            r'|SIP/2\.0\s+\d{3}\b.*)', line)
        if sm:
            cur['startline'] = sm.group(1)
    flush(cur)
    return rows


def _summarize_sip(sip_text):
    """Produce the 'Request: INVITE ...' / 'Status: 200 OK' summary line."""
    sip_text = sip_text.strip()
    # Request line: METHOD sip:uri SIP/2.0
    mreq = re.match(r'^(INVITE|ACK|BYE|CANCEL|REGISTER|OPTIONS|INFO|PRACK|'
                    r'UPDATE|SUBSCRIBE|NOTIFY|MESSAGE|REFER|PUBLISH)\b\s*(\S+)?', sip_text)
    if mreq:
        uri = mreq.group(2) or ''
        return f'Request: {mreq.group(1)} {uri}'.strip()
    # Status line: SIP/2.0 200 OK  (tcpdump may print it without the SIP/2.0 prefix)
    mstat = re.search(r'(?:SIP/2\.0\s+)?(\d{3})\s+(.+?)(?:\s*\(.*)?$', sip_text)
    if mstat and 100 <= int(mstat.group(1)) <= 699:
        return f'Status: {mstat.group(1)} {mstat.group(2).strip()}'
    return sip_text[:120]


def _homer_partitions(window_start, window_end):
    """Yield candidate partition table names overlapping the call window.

    heplify names partitions in UTC by hour. We widen by one hour on each side
    to absorb clock skew and calls straddling an hour boundary.
    """
    from django.utils import timezone as _tz  # noqa: PLC0415
    start = (window_start or window_end)
    end = (window_end or window_start)
    if not start:
        return
    # Normalise to UTC naive hour stamps.
    start = (start - timedelta(hours=1))
    end = (end + timedelta(hours=1))
    if _tz.is_aware(start):
        start = start.astimezone(_dt_utc()).replace(tzinfo=None)
    if _tz.is_aware(end):
        end = end.astimezone(_dt_utc()).replace(tzinfo=None)
    cur = start.replace(minute=0, second=0, microsecond=0)
    while cur <= end:
        suffix = cur.strftime('%Y%m%d_%H00')
        for typ in _HOMER_SIP_TYPES:
            yield f'hep_proto_1_{typ}_{suffix}'
        cur += timedelta(hours=1)


def _dt_utc():
    from datetime import timezone as _z  # noqa: PLC0415
    return _z.utc


def leg_sip_view_homer(call_id, window_start, window_end):
    """Decode one leg's SIP from HOMER by Call-ID. Returns (frames, has_capture).

    Queries each candidate hourly partition for rows whose data_header->>'callid'
    matches, unions them, orders by capture time, and renders the same frame
    rows decode_frames() produces. A missing partition table is skipped (the
    call may predate capture, or the hour rolled). Returns ([], False) when the
    source is disabled, unreachable, or has no matching rows.
    """
    cfg = _homer_settings()
    if not cfg['enabled'] or not call_id:
        return [], False
    try:
        import psycopg2  # noqa: PLC0415
    except ImportError:
        return [], False

    tables = list(_homer_partitions(window_start, window_end))
    if not tables:
        return [], False

    rows = []
    conn = None
    try:
        conn = psycopg2.connect(
            host=cfg['host'], port=cfg['port'], dbname=cfg['name'],
            user=cfg['user'], password=cfg['password'], connect_timeout=3,
        )
        with conn.cursor() as cur:
            # Which candidate partitions actually exist (avoid 'relation does not
            # exist' aborting the whole query).
            cur.execute(
                "select table_name from information_schema.tables "
                "where table_schema='public' and table_name = any(%s)",
                (tables,),
            )
            existing = [r[0] for r in cur.fetchall()]
            if not existing:
                return [], False
            union = ' union all '.join(
                f'select create_date, protocol_header, raw from public."{t}" '
                f"where data_header->>'callid' = %s"
                for t in existing
            )
            cur.execute(union + ' order by create_date', tuple([call_id] * len(existing)))
            for create_date, proto, raw in cur.fetchall():
                rows.append((create_date, proto or {}, raw or ''))
    except Exception:  # noqa: BLE001 — capture source is best-effort; fall back to pcap
        return [], False
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:  # noqa: BLE001
                pass

    if not rows:
        return [], False

    frames = []
    base_ts = None
    for create_date, proto, raw in rows:
        startline = raw.split('\r\n', 1)[0].split('\n', 1)[0].strip()
        if not startline:
            continue
        epoch = create_date.timestamp()
        if base_ts is None:
            base_ts = epoch
        src = proto.get('srcIp', '')
        dst = proto.get('dstIp', '')
        frames.append({
            'n': len(frames) + 1,
            'time': round(epoch - base_ts, 6),
            'src': src, 'dst': dst, 'proto': 'SIP',
            'length': len(raw) if raw else None,
            'info': _summarize_sip(startline),
        })
    return frames, bool(frames)


def leg_sip_view(call_id, window_start, window_end, presliced_path=None,
                 presliced_bytes=None):
    """High-level: decode one leg's SIP. Returns (frames, has_capture).

    Fastest path: presliced_bytes — the pcap stored in the CDR row (bytea). Decode
    straight from the DB, no disk/scan at all.
    Fast path: presliced_path — a per-call pcap file (oversize fallback).
    Slow path: live-slice by Call-ID from the rolling capture (old/un-sliced calls).
    """
    if presliced_bytes:
        with tempfile.NamedTemporaryFile(suffix='.pcap', delete=False) as tmp:
            tmp.write(bytes(presliced_bytes))
            bpath = tmp.name
        try:
            return decode_frames(bpath), True
        finally:
            try:
                os.unlink(bpath)
            except OSError:
                pass

    if presliced_path and os.path.exists(presliced_path) and os.path.getsize(presliced_path) > 24:
        return decode_frames(presliced_path), True

    # Live path: prefer HOMER (captures TLS/wss legs in cleartext). Fall back to
    # slicing the rolling pcap when HOMER is disabled/empty (e.g. calls that
    # predate the HEP rollout).
    homer_frames, homer_ok = leg_sip_view_homer(call_id, window_start, window_end)
    if homer_ok:
        return homer_frames, True

    with tempfile.NamedTemporaryFile(suffix='.pcap', delete=False) as tmp:
        tmp_path = tmp.name
    try:
        sliced = slice_leg_pcap(call_id, window_start, window_end, tmp_path)
        if not sliced:
            return [], False
        return decode_frames(sliced), True
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


def _concat_pcaps(parts, out_path):
    """Concatenate same-linktype pcap files. Writes the first file verbatim, then
    appends each subsequent file's packet records (skipping its 24-byte global
    header). All our capture files share one linktype (LINUX_SLL2), so this is
    valid. Best-effort: a malformed part is skipped."""
    PCAP_GLOBAL_HEADER = 24
    with open(out_path, 'wb') as out:
        for i, p in enumerate(parts):
            try:
                with open(p, 'rb') as fh:
                    data = fh.read()
            except OSError:
                continue
            if len(data) <= PCAP_GLOBAL_HEADER:
                continue
            out.write(data if i == 0 else data[PCAP_GLOBAL_HEADER:])


def _which(prog):
    from shutil import which  # noqa: PLC0415
    return which(prog)
