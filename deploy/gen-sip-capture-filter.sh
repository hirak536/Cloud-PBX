#!/usr/bin/env bash
# Generate the BPF filter for sip-capture.service so we only record SIP that
# belongs to a tenant — i.e. traffic with one of our real peers — and drop the
# open-internet scanner noise that floods :5060.
#
# Strategy (tcpdump filters headers, not SIP content, so "tenant" == "our peers"):
#   - INTERNAL  (5080/5081) + WEBRTC (5066/5067): capture ALL. These are
#     authenticated, registered extensions — the tenant phones themselves.
#   - EXTERNAL  (5060/5061): capture ONLY traffic to/from our carrier gateway
#     IPs (auto-derived from FreeSWITCH's configured gateway proxies). Scanners
#     hammering :5060 from random hosts are not a gateway, so they're excluded.
#
# Output: writes the filter to /etc/sip-capture.bpf (read by the service).
# Re-run this whenever gateways change, then: systemctl restart sip-capture.
set -euo pipefail

FILTER_FILE="${1:-/etc/sip-capture.bpf}"
FS_PASS="${FREESWITCH_PASSWORD:-HoustonFreeSwitchClueCon}"
INTERNAL_PORTS="5080 5081 5066 5067"
EXTERNAL_PORTS="5060 5061"

# --- enumerate gateway proxy IPs (live from FreeSWITCH) -----------------------
gw_ips="$(fs_cli -p "$FS_PASS" -x 'sofia xmlstatus gateway' 2>/dev/null \
  | grep -oE '<proxy>sip:[0-9]{1,3}(\.[0-9]{1,3}){3}' \
  | grep -oE '[0-9]{1,3}(\.[0-9]{1,3}){3}' \
  | sort -u || true)"

if [ -z "$gw_ips" ]; then
  echo "WARNING: no gateway IPs found; external capture will be gateway-empty (internal/webrtc still captured)" >&2
fi

# --- build the filter ---------------------------------------------------------
# internal/webrtc: any packet on those ports
int_clause=""
for p in $INTERNAL_PORTS; do
  int_clause="${int_clause:+$int_clause or }port $p"
done

# external: on 5060/5061 AND host is one of our gateways
ext_ports_clause=""
for p in $EXTERNAL_PORTS; do
  ext_ports_clause="${ext_ports_clause:+$ext_ports_clause or }port $p"
done
ext_host_clause=""
for ip in $gw_ips; do
  ext_host_clause="${ext_host_clause:+$ext_host_clause or }host $ip"
done

if [ -n "$ext_host_clause" ]; then
  external="(($ext_ports_clause) and ($ext_host_clause))"
else
  external=""   # no gateways → capture nothing on the external side
fi

if [ -n "$external" ]; then
  filter="(udp or tcp) and (($int_clause) or $external)"
else
  filter="(udp or tcp) and ($int_clause)"
fi

echo "$filter" > "$FILTER_FILE"
echo "Wrote SIP capture filter to $FILTER_FILE:" >&2
echo "  $filter" >&2
echo "  gateway IPs: ${gw_ips:-<none>}" >&2
