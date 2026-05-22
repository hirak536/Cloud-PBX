"""
One-shot cleanup of bad affinity rows.

The old CDR trigger could mis-fire and write the PSTN caller_id_number into
extension_number (e.g. extension_number='+13465711217'). Real internal
extensions are short digit strings, optionally suffixed with '-TENANTCODE'
(e.g. '901', '901-IHDT'). Drop anything that doesn't match that shape.
"""
from django.db import migrations


FORWARD_SQL = r"""
DELETE FROM v_caller_extension_affinity
WHERE extension_number !~ '^[0-9]{1,6}(-[A-Za-z0-9]+)?$';
"""


class Migration(migrations.Migration):

    dependencies = [
        ('custom_destinations', '0012_drop_affinity_cdr_trigger'),
    ]

    operations = [
        migrations.RunSQL(FORWARD_SQL, migrations.RunSQL.noop),
    ]
