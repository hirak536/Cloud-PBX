from django.db import migrations


class Migration(migrations.Migration):
    # Server-only migration from a merged branch. No-op — absorbed by 0005_merge.
    dependencies = [
        ('working_hours', '0003_remove_workinghoursday_unique_working_hours_day_and_more'),
    ]

    operations = [
    ]
