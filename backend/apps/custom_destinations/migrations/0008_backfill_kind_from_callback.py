"""
Backfill `kind` from the legacy `callback_to_last_caller` flag.
Anyone who had the toggle on becomes kind='sticky_last_agent'; everyone else stays 'simple'.

Idempotent: safe to re-run because it just sets the kind based on existing flags.
"""
from django.db import migrations


def forwards(apps, schema_editor):
    CustomDestination = apps.get_model('custom_destinations', 'CustomDestination')
    CustomDestination.objects.filter(callback_to_last_caller=True).update(kind='sticky_last_agent')


def backwards(apps, schema_editor):
    # No-op: callback_to_last_caller is still authoritative on the way back.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('custom_destinations', '0007_customdestination_kind'),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
