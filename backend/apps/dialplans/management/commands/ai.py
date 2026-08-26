"""
Management command to create the AI assistant dialplan entry for extension 999-DEMO.

Usage:
    python manage.py create_ai_assistant_dialplan --domain 23.189.208.80 \
        --bridge-host <ip-of-gemini-bridge-server> [--bridge-port 5001] [--tenant DEMO]
"""
import uuid
from django.core.management.base import BaseCommand, CommandError
from apps.dialplans.models import Dialplan
from core.models import Domain


AI_DIALPLAN_XML_TEMPLATE = """\
<extension name="AI Assistant (999-DEMO)">
  <condition field="destination_number" expression="^999-DEMO$">
    <action application="answer"/>
    <action application="set" data="tts_engine=none"/>
    <action application="set" data="fire_talk_event=true"/>
    <action application="set" data="RECORD_STEREO=false"/>
    <action application="audio_stream" data="ws://{bridge_host}:{bridge_port}/audio"/>
    <action application="hangup"/>
  </condition>
</extension>"""


class Command(BaseCommand):
    help = "Create the AI assistant dialplan entry for extension 999-DEMO"

    def add_arguments(self, parser):
        parser.add_argument(
            "--domain",
            default="23.189.208.80",
            help="Domain name (default: 23.189.208.80)",
        )
        parser.add_argument(
            "--bridge-host",
            required=True,
            help="IP or hostname of the Gemini bridge WebSocket server",
        )
        parser.add_argument(
            "--bridge-port",
            type=int,
            default=5001,
            help="WebSocket server port (default: 5001)",
        )
        parser.add_argument(
            "--tenant",
            default=None,
            help="Tenant code (e.g. DEMO). Uses default context if omitted.",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Replace existing 999-DEMO dialplan entry if it exists",
        )

    def handle(self, *args, **options):
        domain_name  = options["domain"]
        bridge_host  = options["bridge_host"]
        bridge_port  = options["bridge_port"]
        tenant_code  = options.get("tenant")
        force        = options["force"]

        try:
            domain = Domain.objects.get(domain_name=domain_name, domain_enabled=True)
        except Domain.DoesNotExist:
            raise CommandError(f"Domain '{domain_name}' not found or disabled.")

        context = f"default-{tenant_code}" if tenant_code else "default"

        existing = Dialplan.objects.filter(
            domain=domain,
            dialplan_number="999-DEMO",
            dialplan_context=context,
        ).first()

        if existing:
            if not force:
                self.stdout.write(self.style.WARNING(
                    f"Dialplan entry for 999-DEMO already exists (UUID: {existing.dialplan_uuid}). "
                    "Use --force to overwrite."
                ))
                return
            existing.delete()
            self.stdout.write("Removed existing 999-DEMO dialplan entry.")

        xml = AI_DIALPLAN_XML_TEMPLATE.format(
            bridge_host=bridge_host,
            bridge_port=bridge_port,
        )

        dp = Dialplan.objects.create(
            domain=domain,
            dialplan_context=context,
            dialplan_name="AI Assistant (999-DEMO)",
            dialplan_number="999-DEMO",
            dialplan_destination=False,
            dialplan_continue="",
            dialplan_xml=xml,
            dialplan_order=200,
            dialplan_enabled=True,
            dialplan_global=False,
            dialplan_description=(
                f"Gemini Live AI assistant. Streams audio to ws://{bridge_host}:{bridge_port}/audio"
            ),
        )

        self.stdout.write(self.style.SUCCESS(
            f"Created dialplan entry for 999-DEMO\n"
            f"  UUID:    {dp.dialplan_uuid}\n"
            f"  Context: {context}\n"
            f"  Bridge:  ws://{bridge_host}:{bridge_port}/audio\n"
            f"\n"
            f"Next steps:\n"
            f"  1. Start the bridge:  GEMINI_API_KEY=AQ... python gemini_ai_bridge.py\n"
            f"  2. Ensure port {bridge_port} is reachable from FreeSWITCH ({bridge_host})\n"
            f"  3. Dial 999-DEMO from any extension to test\n"
        ))

