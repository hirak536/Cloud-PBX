from django.db import migrations

KEY = 'on_demand_recording'
NUMBER = '*2'


def seed(apps, schema_editor):
    FeatureCode = apps.get_model('feature_codes', 'FeatureCode')
    # tenant=None / domain=None is the existing convention for a global code
    # (see the seeded eavesdrop and voicemail rows). Idempotent so re-running
    # against a DB that already has the row is a no-op.
    if FeatureCode.objects.filter(feature_code_key=KEY, tenant__isnull=True).exists():
        return
    FeatureCode.objects.create(
        feature_code_name='On-Demand Call Recording',
        feature_code_key=KEY,
        feature_code_number=NUMBER,
        feature_code_enabled=True,
        feature_code_description=(
            'Pressed mid-call to start or stop recording the current call. '
            'Only the internal party can trigger it. Starting plays a recorded '
            'notice to both parties; stopping plays a "recording stopped" notice.'
        ),
    )


def unseed(apps, schema_editor):
    FeatureCode = apps.get_model('feature_codes', 'FeatureCode')
    FeatureCode.objects.filter(feature_code_key=KEY, tenant__isnull=True).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('feature_codes', '0003_feature_code_key_number_enabled'),
    ]

    operations = [
        migrations.RunPython(seed, unseed),
    ]
