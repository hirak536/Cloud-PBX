from django.db import migrations


class Migration(migrations.Migration):
    # Server-only migration from a merged branch. No-op — absorbed by 0012_merge.
    dependencies = [
        ('destinations', '0008_destination_callback_to_last_caller'),
    ]

    operations = [
    ]
