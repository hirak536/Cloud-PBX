#!/usr/bin/env python3
"""
reg_blf_offline.py  —  IHS-PBX

Bridges a FreeSWITCH limitation: on a dialog/BLF subscription, FreeSWITCH does
NOT signal "offline" when a monitored extension unregisters, so the watcher's
BLF lamp stays at its last value (usually green). Grandstream UCM publishes an
offline state on unregister; plain FreeSWITCH does not. This daemon replicates
that: it listens on the FreeSWITCH event_socket for sofia register / unregister
/ expire and re-publishes a presence (PRESENCE_IN) for the affected AOR so the
watcher's lamp updates.

Why an external event_socket daemon (not a startup-script Lua hook):
  mod_lua is non-unloadable on this box, so a Lua EventConsumer thread can only
  be stopped by restarting FreeSWITCH. This process can be killed instantly
  (Ctrl-C / kill / systemd stop) with zero impact on calls. Fully reversible.

Safety:
  * Single extension allow-list during testing (--only 909-IHDT) so we never
    touch other lamps while validating.
  * --offline-state lets us tune what we publish (terminated / confirmed /
    closed) until we find the one that greys the phone, without code edits.
  * Logs every publish; no state is persisted.

Usage (test on one ext):
  python3 reg_blf_offline.py --only 909-IHDT --offline-state closed --dry-run
  python3 reg_blf_offline.py --only 909-IHDT --offline-state closed
Roll out (all extensions) only after the phone is confirmed greying:
  python3 reg_blf_offline.py --offline-state closed
"""
import argparse, socket, sys, time, uuid

ESL_HOST = "127.0.0.1"
ESL_PORT = 8021
ESL_PASS = "HoustonFreeSwitchClueCon"


def esl_connect():
    s = socket.create_connection((ESL_HOST, ESL_PORT), timeout=10)
    f = s.makefile("rwb")
    _read_block(f)                       # auth/request
    f.write(b"auth %s\n\n" % ESL_PASS.encode())
    f.flush()
    _read_block(f)                       # auth reply
    s.settimeout(None)                   # event loop blocks indefinitely on reads
    return s, f


def _read_block(f):
    """Read one event_socket block: headers until blank line, then body if any."""
    headers = {}
    while True:
        line = f.readline()
        if not line:
            return None, ""
        line = line.decode(errors="replace").rstrip("\r\n")
        if line == "":
            break
        if ":" in line:
            k, v = line.split(":", 1)
            headers[k.strip().lower()] = v.strip()
    body = ""
    n = headers.get("content-length")
    if n:
        body = f.read(int(n)).decode(errors="replace")
    return headers, body


def parse_event(body):
    """event_socket 'plain' event body -> dict of lowercased headers."""
    ev = {}
    for line in body.splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            ev[k.strip().lower()] = v.strip()
    return ev


def publish(f, user, domain, online, offline_state, dry):
    """Fire a PRESENCE_IN for user@domain. online=True -> hand back to native
    call-state (terminated/green). online=False -> publish the configured
    offline state (terminated|confirmed|closed)."""
    eid = str(uuid.uuid4())
    if online:
        answer, status, rpid, oc = "terminated", "Available", "unknown", "open"
    else:
        # 'closed' is rendered grey by Grandstream presence; for dialog watchers
        # 'confirmed' is the only non-green dialog state. We let the operator pick.
        if offline_state == "confirmed":
            answer, status, rpid, oc = "confirmed", "Unregistered", "busy", "closed"
        elif offline_state == "terminated":
            answer, status, rpid, oc = "terminated", "Unregistered", "away", "closed"
        else:  # "closed"  (PIDF basic=closed via rpid + open_closed)
            answer, status, rpid, oc = "terminated", "Unregistered", "away", "closed"

    cmd = (
        "sendevent PRESENCE_IN\n"
        "proto: sip\n"
        "event_type: presence\n"
        "alt_event_type: dialog\n"
        "Presence-Call-Direction: outbound\n"
        "from: %s@%s\n"
        "login: %s@%s\n"
        "unique-id: %s\n"
        "answer-state: %s\n"
        "rpid: %s\n"
        "status: %s\n"
        "open_closed: %s\n"
        "event_count: 1\n"
        "\n"
    ) % (user, domain, user, domain, eid, answer, rpid, status, oc)

    label = "GREEN/online" if online else ("OFFLINE/" + offline_state)
    print("[reg_blf_offline] %s  %s@%s  (answer=%s oc=%s)%s"
          % (label, user, domain, answer, oc, "  [DRY-RUN]" if dry else ""), flush=True)
    if dry:
        return
    f.write(cmd.encode())
    f.flush()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default=None,
                    help="restrict to a single AOR user, e.g. 909-IHDT (test mode)")
    ap.add_argument("--offline-state", default="closed",
                    choices=["closed", "terminated", "confirmed"],
                    help="what to publish when an ext unregisters")
    ap.add_argument("--dry-run", action="store_true",
                    help="log what would be published, send nothing")
    args = ap.parse_args()

    s, f = esl_connect()
    f.write(b"events plain CUSTOM sofia::register sofia::unregister sofia::expire\n\n")
    f.flush()
    _read_block(f)
    print("[reg_blf_offline] started  only=%s  offline-state=%s  dry=%s"
          % (args.only, args.offline_state, args.dry_run), flush=True)

    while True:
        headers, body = _read_block(f)
        if headers is None:
            print("[reg_blf_offline] ESL closed, reconnecting in 2s", flush=True)
            time.sleep(2)
            try:
                s.close()
            except Exception:
                pass
            s, f = esl_connect()
            f.write(b"events plain CUSTOM sofia::register sofia::unregister sofia::expire\n\n")
            f.flush()
            _read_block(f)
            continue
        if headers.get("content-type") != "text/event-plain":
            continue
        ev = parse_event(body)
        subclass = ev.get("event-subclass", "")
        user = ev.get("username") or ev.get("from-user")
        domain = ev.get("domain_name") or ev.get("from-host")
        expires = ev.get("expires")
        if not user or not domain:
            continue
        if args.only and user != args.only:
            continue

        if subclass == "sofia::register" and expires not in ("0", None):
            publish(f, user, domain, True, args.offline_state, args.dry_run)
        elif subclass in ("sofia::unregister", "sofia::expire") or expires == "0":
            publish(f, user, domain, False, args.offline_state, args.dry_run)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[reg_blf_offline] stopped", flush=True)
        sys.exit(0)
