import subprocess
import re
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated


# Absolute paths: /usr/sbin is not always on the service PATH, and the
# process already runs as root so no privilege escalation wrapper is needed.
_BINARIES = {
    'fail2ban-client': '/usr/bin/fail2ban-client',
    'ufw': '/usr/sbin/ufw',
}


def run(cmd):
    if cmd and cmd[0] in _BINARIES:
        cmd = [_BINARIES[cmd[0]]] + cmd[1:]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return '', 1
    return result.stdout.strip(), result.returncode


class Fail2banStatusView(APIView):
    """List all jails and their banned IPs."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        stdout, rc = run(['fail2ban-client', 'status'])
        if rc != 0:
            return Response({'error': 'fail2ban not available'}, status=503)

        # Parse jail list
        jails = []
        match = re.search(r'Jail list:\s+(.+)', stdout)
        if match:
            jails = [j.strip() for j in match.group(1).split(',') if j.strip()]

        result = []
        for jail in jails:
            out, _ = run(['fail2ban-client', 'status', jail])
            banned_ips = []
            m = re.search(r'Banned IP list:\s+(.*)', out)
            if m and m.group(1).strip():
                banned_ips = m.group(1).strip().split()
            currently_failed = 0
            mf = re.search(r'Currently failed:\s+(\d+)', out)
            if mf:
                currently_failed = int(mf.group(1))
            total_banned = 0
            mt = re.search(r'Total banned:\s+(\d+)', out)
            if mt:
                total_banned = int(mt.group(1))

            # Parse failing IPs from fail2ban log for this jail
            failing_ips = []
            log_files = []
            lf = re.search(r'File list:\s+(.*)', out)
            if lf:
                log_files = lf.group(1).strip().split()
            for log_file in log_files:
                try:
                    grep_out, _ = run(['grep', '-h', 'WARNING.*sofia_reg', log_file])
                    seen = set()
                    for line in grep_out.splitlines():
                        ip_m = re.search(r'from\s+\[?([\d\.]+)\]?\s*$', line)
                        if ip_m:
                            ip = ip_m.group(1)
                            if ip not in seen and ip not in banned_ips:
                                seen.add(ip)
                                failing_ips.append(ip)
                except Exception:
                    pass

            result.append({
                'jail': jail,
                'banned_ips': banned_ips,
                'failing_ips': failing_ips,
                'currently_failed': currently_failed,
                'total_banned': total_banned,
            })

        return Response(result)


class Fail2banBanView(APIView):
    """Ban an IP in a specific jail."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        ip = request.data.get('ip', '').strip()
        jail = request.data.get('jail', 'recidive').strip()

        if not ip:
            return Response({'error': 'ip is required'}, status=400)

        if not re.match(r'^[\d\.:a-fA-F]+$', ip):
            return Response({'error': 'invalid IP address'}, status=400)

        out, rc = run(['fail2ban-client', 'set', jail, 'banip', ip])
        return Response({'result': out, 'jail': jail, 'ip': ip})


class Fail2banUnbanView(APIView):
    """Unban an IP from a jail (or all jails)."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        ip = request.data.get('ip', '').strip()
        jail = request.data.get('jail', '').strip()

        if not ip:
            return Response({'error': 'ip is required'}, status=400)

        # Validate IP format
        if not re.match(r'^[\d\.:a-fA-F]+$', ip):
            return Response({'error': 'invalid IP address'}, status=400)

        if jail:
            out, rc = run(['fail2ban-client', 'set', jail, 'unbanip', ip])
            return Response({'result': out, 'jail': jail, 'ip': ip})
        else:
            # Try all jails
            stdout, _ = run(['fail2ban-client', 'status'])
            jails = []
            match = re.search(r'Jail list:\s+(.+)', stdout)
            if match:
                jails = [j.strip() for j in match.group(1).split(',') if j.strip()]
            results = []
            for j in jails:
                out, _ = run(['fail2ban-client', 'set', j, 'unbanip', ip])
                results.append({'jail': j, 'result': out})
            return Response({'results': results, 'ip': ip})


class Fail2banWhitelistView(APIView):
    """Add an IP to the ignore list for a jail."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        ip = request.data.get('ip', '').strip()
        jail = request.data.get('jail', 'sshd').strip()

        if not ip:
            return Response({'error': 'ip is required'}, status=400)

        if not re.match(r'^[\d\.:a-fA-F/]+$', ip):
            return Response({'error': 'invalid IP address'}, status=400)

        out, rc = run(['fail2ban-client', 'set', jail, 'addignoreip', ip])
        return Response({'result': out, 'jail': jail, 'ip': ip})


class UfwStatusView(APIView):
    """UFW status with numbered rules."""
    permission_classes = [IsAuthenticated]

    def get(self, _request):
        out, rc = run(['ufw', 'status', 'verbose'])
        if rc != 0:
            return Response({'error': 'ufw not available'}, status=503)
        status_line = 'inactive'
        for line in out.splitlines():
            if line.lower().startswith('status:'):
                status_line = line.split(':', 1)[1].strip()
                break

        out_numbered, _ = run(['ufw', 'status', 'numbered'])
        rules = []
        for line in out_numbered.splitlines():
            m = re.match(r'\[\s*(\d+)\]\s+(.*)', line)
            if not m:
                continue
            raw = m.group(2).strip()
            # Parse: "to   action   from" or "to (v6)  action  from"
            # UFW columns are whitespace-separated but action is multi-word
            p = re.match(
                r'^(.+?)\s{2,}(ALLOW\s*(?:FWD|IN|OUT)?|DENY\s*(?:FWD|IN|OUT)?|REJECT\s*(?:FWD|IN|OUT)?|LIMIT\s*(?:FWD|IN|OUT)?)\s{2,}(.+)$',
                raw, re.IGNORECASE
            )
            if p:
                to_part = p.group(1).strip()
                action_part = p.group(2).strip().upper()
                from_part = p.group(3).strip()
                # Separate action verb from direction
                action_words = action_part.split()
                action_verb = action_words[0]
                direction = action_words[1] if len(action_words) > 1 else 'IN'
                rules.append({
                    'num': int(m.group(1)),
                    'to': to_part,
                    'action': action_verb,
                    'direction': direction,
                    'from_': from_part,
                    'raw': raw,
                })
            else:
                rules.append({'num': int(m.group(1)), 'to': raw, 'action': '', 'direction': '', 'from_': '', 'raw': raw})

        return Response({'status': status_line, 'rules': rules})

    def post(self, request):
        """Add a UFW rule.

        Every field is validated against a strict pattern and passed as a
        separate argv element -- these arguments reach a root-privileged
        binary, so no user input may be interpolated into a shell string.
        """
        action = str(request.data.get('action', 'allow')).strip().lower()
        if action not in ('allow', 'deny', 'reject', 'limit'):
            return Response({'error': 'action must be allow, deny, reject or limit'}, status=400)

        direction = str(request.data.get('direction', 'in')).strip().lower()
        if direction not in ('in', 'out'):
            return Response({'error': 'direction must be in or out'}, status=400)

        port = str(request.data.get('port', '')).strip()
        proto = str(request.data.get('proto', '')).strip().lower()
        from_ip = str(request.data.get('from_ip', '')).strip()
        comment = str(request.data.get('comment', '')).strip()

        if proto and proto not in ('tcp', 'udp'):
            return Response({'error': 'proto must be tcp or udp'}, status=400)

        # Single port (80) or an inclusive range (16384:32768).
        if port and not re.match(r'^\d{1,5}(:\d{1,5})?$', port):
            return Response({'error': 'port must be a number or range like 16384:32768'}, status=400)
        for p in (port.split(':') if port else []):
            if not 1 <= int(p) <= 65535:
                return Response({'error': 'port must be between 1 and 65535'}, status=400)

        # ufw itself rejects a multi-port range without an explicit protocol.
        if ':' in port and not proto:
            return Response({'error': 'a port range requires proto tcp or udp'}, status=400)

        # IPv4/IPv6 address or CIDR, or the literal "any".
        if from_ip and from_ip.lower() != 'any' \
                and not re.match(r'^[\da-fA-F:.]+(/\d{1,3})?$', from_ip):
            return Response({'error': 'invalid source address'}, status=400)

        if comment and not re.match(r'^[\w .,:/#()+-]{1,120}$', comment):
            return Response({'error': 'comment contains unsupported characters'}, status=400)

        if not port and not from_ip:
            return Response({'error': 'specify a port, a source address, or both'}, status=400)

        cmd = ['ufw', action, direction]
        if from_ip and from_ip.lower() != 'any':
            cmd += ['from', from_ip]
            if port:
                cmd += ['to', 'any', 'port', port]
        elif port:
            cmd += [f'{port}/{proto}' if proto else port]
        if from_ip and from_ip.lower() != 'any' and port and proto:
            cmd += ['proto', proto]
        if comment:
            cmd += ['comment', comment]

        out, rc = run(cmd)
        if rc != 0:
            return Response({'error': out or 'ufw rejected the rule', 'command': ' '.join(cmd)},
                            status=400)
        return Response({'result': out, 'command': ' '.join(cmd)}, status=201)

    def delete(self, request):
        """Delete a UFW rule by its number from `ufw status numbered`.

        Rule numbers shift after every deletion, so the client must send the
        rule text it intends to remove; it is re-read here and compared before
        deleting to avoid removing whatever slid into that slot.
        """
        num = request.data.get('num')
        try:
            num = int(num)
        except (TypeError, ValueError):
            return Response({'error': 'num must be an integer'}, status=400)
        if num < 1:
            return Response({'error': 'num must be 1 or greater'}, status=400)

        expect = str(request.data.get('raw', '')).strip()

        out, rc = run(['ufw', 'status', 'numbered'])
        if rc != 0:
            return Response({'error': 'ufw not available'}, status=503)

        current = None
        for line in out.splitlines():
            m = re.match(r'\[\s*(\d+)\]\s+(.*)', line)
            if m and int(m.group(1)) == num:
                current = m.group(2).strip()
                break
        if current is None:
            return Response({'error': f'no rule numbered {num}'}, status=404)

        if expect and ' '.join(expect.split()) != ' '.join(current.split()):
            return Response({
                'error': 'rule numbers changed since the list was loaded; refresh and retry',
                'expected': expect,
                'found': current,
            }, status=409)

        # --force skips ufw's interactive "Proceed (y|n)?" prompt.
        out, rc = run(['ufw', '--force', 'delete', str(num)])
        if rc != 0:
            return Response({'error': out or 'ufw delete failed'}, status=400)
        return Response({'result': out, 'num': num, 'deleted': current})


class IptablesView(APIView):
    """Check if an IP is blocked in iptables."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        ip = request.query_params.get('ip', '').strip()
        if not ip:
            return Response({'error': 'ip query param required'}, status=400)

        if not re.match(r'^[\d\.:a-fA-F]+$', ip):
            return Response({'error': 'invalid IP address'}, status=400)

        # Scan every chain, not just INPUT: fail2ban puts bans in its own
        # f2b-* sub-chains that INPUT only jumps to, so listing INPUT alone
        # never shows a banned IP.
        out, rc = run(['iptables', '-L', '-n', '--line-numbers'])
        if rc != 0:
            return Response({'error': 'iptables not available'}, status=503)

        chain = ''
        matches = []
        for line in out.splitlines():
            cm = re.match(r'^Chain\s+(\S+)', line)
            if cm:
                chain = cm.group(1)
                continue
            # Match the source column exactly so 1.2.3.4 does not hit 1.2.3.45
            if re.search(r'(?<![\d.])' + re.escape(ip) + r'(?:/\d+)?(?![\d.])', line):
                matches.append({'chain': chain, 'rule': line.strip()})

        return Response({
            'ip': ip,
            'blocked': len(matches) > 0,
            'chains': sorted({m['chain'] for m in matches}),
            'rules': [f"{m['chain']}: {m['rule']}" for m in matches],
        })

    def delete(self, request):
        """Unblock an IP wherever it is actually blocked.

        A raw `iptables -D` against an f2b-* chain leaves fail2ban's database
        believing the IP is still banned, so it never re-bans and the rule can
        reappear. Any IP held by a fail2ban jail is therefore released through
        fail2ban-client; only non-fail2ban rules are deleted directly.
        """
        ip = request.data.get('ip', '').strip()
        chain = request.data.get('chain', '').strip()

        if not ip:
            return Response({'error': 'ip is required'}, status=400)

        if not re.match(r'^[\d\.:a-fA-F]+$', ip):
            return Response({'error': 'invalid IP address'}, status=400)

        if chain and chain not in ('INPUT', 'OUTPUT', 'FORWARD') \
                and not re.match(r'^f2b-[\w.-]+$', chain):
            return Response({'error': 'invalid chain'}, status=400)

        ip_re = re.compile(r'(?<![\d.])' + re.escape(ip) + r'(?:/\d+)?(?![\d.])')

        # Release from every fail2ban jail that currently holds this IP.
        unbanned_jails = []
        status_out, status_rc = run(['fail2ban-client', 'status'])
        if status_rc == 0:
            jm = re.search(r'Jail list:\s+(.+)', status_out)
            for jail in (j.strip() for j in jm.group(1).split(',')) if jm else []:
                if not jail:
                    continue
                jail_out, _ = run(['fail2ban-client', 'status', jail])
                bl = re.search(r'Banned IP list:\s+(.*)', jail_out)
                if bl and ip in bl.group(1).split():
                    _, urc = run(['fail2ban-client', 'set', jail, 'unbanip', ip])
                    if urc == 0:
                        unbanned_jails.append(jail)

        # Delete any remaining raw rules, skipping f2b-* chains (fail2ban owns
        # those and has just been asked to clean them up itself).
        deleted = 0
        residual_chains = []
        list_cmd = ['iptables', '-L', '-n', '--line-numbers']
        if chain:
            list_cmd = ['iptables', '-L', chain, '-n', '--line-numbers']
        out, rc = run(list_cmd)
        if rc != 0:
            return Response({'error': 'cannot read iptables rules'}, status=503)

        current = chain
        hits = {}
        for line in out.splitlines():
            cm = re.match(r'^Chain\s+(\S+)', line)
            if cm:
                current = cm.group(1)
                continue
            parts = line.split()
            if not (parts and parts[0].isdigit()):
                continue
            if ip_re.search(line):
                hits.setdefault(current, []).append(int(parts[0]))

        for target_chain, numbers in hits.items():
            if target_chain.startswith('f2b-'):
                residual_chains.append(target_chain)
                continue
            # Descending order so earlier deletions don't shift later indexes.
            for num in sorted(numbers, reverse=True):
                _, drc = run(['iptables', '-D', target_chain, str(num)])
                if drc == 0:
                    deleted += 1

        if not unbanned_jails and not deleted:
            return Response({
                'ip': ip,
                'unbanned_jails': [],
                'deleted': 0,
                'message': f'{ip} is not currently blocked',
            })

        return Response({
            'ip': ip,
            'unbanned_jails': unbanned_jails,
            'deleted': deleted,
            'residual_f2b_chains': residual_chains,
        })
