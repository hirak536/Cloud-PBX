from django.db import migrations


class Migration(migrations.Migration):
    # Server-only migration from a merged branch. No-op — absorbed by 0006_merge.
    dependencies = [
        ('xml_cdr', '0004_add_bypass_media'),
    ]

    operations = [
    ]
