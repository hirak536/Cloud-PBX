import re
from django.http import HttpResponse, Http404
from django.views import View
from apps.devices.models import Device, DeviceLine

VENDOR_TEMPLATES = {
    'yealink': 'provision/yealink.cfg',
    'grandstream': 'provision/grandstream.cfg',
    'polycom': 'provision/polycom.cfg',
    'cisco': 'provision/cisco.cfg',
    'snom': 'provision/snom.cfg',
}

class ProvisionView(View):
    """
    Serves device-specific provisioning config files.
    FreeSWITCH phones call this at boot: GET /provision/<mac>/
    """
    def get(self, request, mac, *args, **kwargs):
        mac_clean = re.sub(r'[^0-9a-fA-F]', '', mac).lower()
        try:
            device = Device.objects.select_related('domain').prefetch_related('lines').get(
                device_mac_address__iexact=mac_clean, device_enabled=True
            )
        except Device.DoesNotExist:
            raise Http404(f'Device {mac_clean} not found or not enabled')

        vendor = (device.device_vendor or '').lower()
        config = self._generate_config(device, vendor)
        content_type = 'text/plain'
        if 'xml' in vendor or vendor == 'polycom':
            content_type = 'application/xml'
        return HttpResponse(config, content_type=content_type)

    def _generate_config(self, device, vendor):
        lines = list(device.lines.filter(device_line_enabled=True))
        if vendor == 'yealink':
            return self._yealink_config(device, lines)
        elif vendor == 'grandstream':
            return self._grandstream_config(device, lines)
        elif vendor == 'polycom':
            return self._polycom_config(device, lines)
        else:
            return self._generic_config(device, lines)

    def _yealink_config(self, device, lines):
        cfg = ['#!version:1.0.0.1']
        cfg.append(f'local_time.ntp_server1 = pool.ntp.org')
        cfg.append(f'sip.reg_on = 1')
        for i, line in enumerate(lines, 1):
            cfg.append(f'account.{i}.enable = 1')
            cfg.append(f'account.{i}.label = {line.device_line_label or line.device_line_username}')
            cfg.append(f'account.{i}.display_name = {line.device_line_display_name}')
            cfg.append(f'account.{i}.auth_name = {line.device_line_auth_id or line.device_line_username}')
            cfg.append(f'account.{i}.user_name = {line.device_line_username}')
            cfg.append(f'account.{i}.password = {line.device_line_password}')
            cfg.append(f'account.{i}.sip_server_host = {line.device_line_server_address}')
        return '\n'.join(cfg)

    def _grandstream_config(self, device, lines):
        cfg = ['<?xml version="1.0" encoding="UTF-8"?>', '<gs_provision version="1">',
               '  <config version="1">']
        for i, line in enumerate(lines, 1):
            cfg.append(f'    <P{35+i}>{line.device_line_server_address}</P{35+i}>')
            cfg.append(f'    <P{400+i}>{line.device_line_username}</P{400+i}>')
            cfg.append(f'    <P{404+i}>{line.device_line_auth_id or line.device_line_username}</P{404+i}>')
            cfg.append(f'    <P{8+i}>{line.device_line_password}</P{8+i}>')
            cfg.append(f'    <P{23+i}>{line.device_line_display_name}</P{23+i}>')
        cfg += ['  </config>', '</gs_provision>']
        return '\n'.join(cfg)

    def _polycom_config(self, device, lines):
        cfg = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>', '<APPLICATION>']
        for i, line in enumerate(lines, 1):
            cfg.append(f'  <REG reg.1.address="{line.device_line_username}"')
            cfg.append(f'       reg.1.auth.userId="{line.device_line_auth_id or line.device_line_username}"')
            cfg.append(f'       reg.1.auth.password="{line.device_line_password}"')
            cfg.append(f'       reg.1.server.1.address="{line.device_line_server_address}" />')
        cfg.append('</APPLICATION>')
        return '\n'.join(cfg)

    def _generic_config(self, device, lines):
        cfg = [f'# Generic provisioning config for {device.device_vendor} {device.device_mac_address}']
        for i, line in enumerate(lines, 1):
            cfg.append(f'line{i}_server={line.device_line_server_address}')
            cfg.append(f'line{i}_user={line.device_line_username}')
            cfg.append(f'line{i}_pass={line.device_line_password}')
        return '\n'.join(cfg)
