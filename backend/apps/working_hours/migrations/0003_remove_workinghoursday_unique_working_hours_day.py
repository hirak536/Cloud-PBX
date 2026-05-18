from django.db import migrations


class Migration(migrations.Migration):
    # Server-only migration from a merged branch. No-op — absorbed by 0005_merge.
    dependencies = [
        ('working_hours', '0002_remove_unique_day_constraint'),
    ]

    operations = [
    ]
