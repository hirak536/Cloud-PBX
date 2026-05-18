from django.core.management.base import BaseCommand
from core.models import Domain

class Command(BaseCommand):
    help = 'Create the default domain if it does not exist'

    def add_arguments(self, parser):
        parser.add_argument('domain_name', nargs='?', default='localhost',
                            help='Domain name (default: localhost)')

    def handle(self, *args, **options):
        name = options['domain_name']
        domain, created = Domain.objects.get_or_create(
            domain_name=name,
            defaults={'domain_enabled': True, 'domain_description': 'Default domain'}
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f'Created domain: {name} ({domain.domain_uuid})'))
        else:
            self.stdout.write(f'Domain already exists: {name} ({domain.domain_uuid})')
