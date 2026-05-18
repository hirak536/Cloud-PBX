import subprocess
import re
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated


def run(cmd):
    if cmd and cmd[0] in ('fail2ban-client', 'ufw'):
        cmd = ['sudo'] + cmd
    result = subprocess.run(cmd, capture_output=True, text=True)
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


class IptablesView(APIView):
    """Check if an IP is blocked in iptables."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        ip = request.query_params.get('ip', '').strip()
        if not ip:
            return Response({'error': 'ip query param required'}, status=400)

        if not re.match(r'^[\d\.:a-fA-F]+$', ip):
            return Response({'error': 'invalid IP address'}, status=400)

        out, _ = run(['iptables', '-L', 'INPUT', '-n', '--line-numbers'])
        lines = [l for l in out.splitlines() if ip in l]
        return Response({'ip': ip, 'blocked': len(lines) > 0, 'rules': lines})

    def delete(self, request):
        ip = request.data.get('ip', '').strip()
        chain = request.data.get('chain', 'INPUT').strip()

        if not ip:
            return Response({'error': 'ip is required'}, status=400)

        if not re.match(r'^[\d\.:a-fA-F]+$', ip):
            return Response({'error': 'invalid IP address'}, status=400)

        if chain not in ('INPUT', 'OUTPUT', 'FORWARD'):
            return Response({'error': 'invalid chain'}, status=400)

        # Find matching rule line numbers (reverse order to delete correctly)
        out, _ = run(['iptables', '-L', chain, '-n', '--line-numbers'])
        line_numbers = []
        for line in out.splitlines():
            if ip in line:
                parts = line.split()
                if parts and parts[0].isdigit():
                    line_numbers.append(int(parts[0]))

        if not line_numbers:
            return Response({'message': f'{ip} not found in {chain}', 'deleted': 0})

        deleted = 0
        for num in sorted(line_numbers, reverse=True):
            _, rc = run(['iptables', '-D', chain, str(num)])
            if rc == 0:
                deleted += 1

        return Response({'ip': ip, 'chain': chain, 'deleted': deleted})
