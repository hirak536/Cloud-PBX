from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('custom_destinations', '0008_backfill_kind_from_callback'),
        ('custom_destinations', '0013_cleanup_bad_affinity_rows'),
    ]

    operations = []
