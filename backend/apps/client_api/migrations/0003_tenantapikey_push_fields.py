from django.db import migrations


class Migration(migrations.Migration):
    """Push notification fields were moved to core.Tenant — nothing to add here."""

    dependencies = [
        ('client_api', '0002_masterapikey'),
    ]

    operations = []
