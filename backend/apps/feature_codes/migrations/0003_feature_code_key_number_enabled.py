from django.db import migrations, models


class Migration(migrations.Migration):
    """Sync the model with columns that already exist on v_feature_codes.

    feature_code_key / feature_code_number / feature_code_enabled are present in
    the database (FusionPBX-legacy table) but were missing from the Django model,
    so they were invisible to the ORM. This is a STATE-ONLY migration: adding
    them for real would fail with 'column already exists'.
    """

    dependencies = [
        ('feature_codes', '0002_add_tenant'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.AddField(
                    model_name='featurecode',
                    name='feature_code_key',
                    field=models.CharField(blank=True, default='', max_length=64),
                ),
                migrations.AddField(
                    model_name='featurecode',
                    name='feature_code_number',
                    field=models.CharField(blank=True, default='', max_length=32),
                ),
                migrations.AddField(
                    model_name='featurecode',
                    name='feature_code_enabled',
                    field=models.BooleanField(default=True),
                ),
            ],
        ),
    ]
