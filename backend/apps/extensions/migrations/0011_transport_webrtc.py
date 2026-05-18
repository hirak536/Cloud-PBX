from django.db import migrations


class Migration(migrations.Migration):
    # Server-only migration from a merged branch. No-op — absorbed by 0012_merge.
    dependencies = [
        ('extensions', '0010_add_outbound_did'),
    ]

    operations = [
    ]
