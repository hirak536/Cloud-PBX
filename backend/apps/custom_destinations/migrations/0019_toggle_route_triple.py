"""
0019 — BLF toggle ON/OFF route as a type+target triple.

The toggle ON/OFF branches used to be foreign keys to another CustomDestination
(toggle_on_dest_uuid / toggle_off_dest_uuid). To let a BLF toggle route to ANY
destination (extension, IVR, ring group, voicemail, external number, hangup,
or another custom destination) — the same options the extension route dropdown
offers — store each branch as a (type, target_uuid, external) triple instead.

The old FK columns are kept (not dropped) for back-compat/rollback. This
migration adds the new columns and backfills them from the old FKs so existing
toggles keep routing to their custom destination.

v_custom_destinations is a FusionPBX-owned table; AddField may not alter it
reliably, so columns are added with idempotent raw SQL.
"""
from django.db import migrations, models


ADD_COLS_SQL = """
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name='v_custom_destinations' AND column_name='toggle_on_type') THEN
        ALTER TABLE v_custom_destinations
            ADD COLUMN toggle_on_type varchar(32) NOT NULL DEFAULT '',
            ADD COLUMN toggle_on_target_uuid varchar(64) NOT NULL DEFAULT '',
            ADD COLUMN toggle_on_external varchar(64) NOT NULL DEFAULT '',
            ADD COLUMN toggle_off_type varchar(32) NOT NULL DEFAULT '',
            ADD COLUMN toggle_off_target_uuid varchar(64) NOT NULL DEFAULT '',
            ADD COLUMN toggle_off_external varchar(64) NOT NULL DEFAULT '';
    END IF;
END $$;
"""

# Backfill: a legacy ON/OFF FK pointed at another CustomDestination, so the new
# branch type is 'custom_destination' and the target is that row's uuid.
BACKFILL_SQL = """
UPDATE v_custom_destinations
   SET toggle_on_type = 'custom_destination',
       toggle_on_target_uuid = toggle_on_dest_uuid::text
 WHERE toggle_on_dest_uuid IS NOT NULL
   AND (toggle_on_type IS NULL OR toggle_on_type = '');

UPDATE v_custom_destinations
   SET toggle_off_type = 'custom_destination',
       toggle_off_target_uuid = toggle_off_dest_uuid::text
 WHERE toggle_off_dest_uuid IS NOT NULL
   AND (toggle_off_type IS NULL OR toggle_off_type = '');
"""


class Migration(migrations.Migration):

    dependencies = [
        ('custom_destinations', '0018_customdestination_toggle_state_and_more'),
    ]

    operations = [
        # Keep Django's model state in sync (state_operations) while doing the
        # real schema change via raw SQL on the FusionPBX table.
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddField('customdestination', 'toggle_on_type',
                                    models.CharField(max_length=32, blank=True, default='')),
                migrations.AddField('customdestination', 'toggle_on_target_uuid',
                                    models.CharField(max_length=64, blank=True, default='')),
                migrations.AddField('customdestination', 'toggle_on_external',
                                    models.CharField(max_length=64, blank=True, default='')),
                migrations.AddField('customdestination', 'toggle_off_type',
                                    models.CharField(max_length=32, blank=True, default='')),
                migrations.AddField('customdestination', 'toggle_off_target_uuid',
                                    models.CharField(max_length=64, blank=True, default='')),
                migrations.AddField('customdestination', 'toggle_off_external',
                                    models.CharField(max_length=64, blank=True, default='')),
            ],
            database_operations=[
                migrations.RunSQL(sql=ADD_COLS_SQL, reverse_sql=migrations.RunSQL.noop),
            ],
        ),
        migrations.RunSQL(sql=BACKFILL_SQL, reverse_sql=migrations.RunSQL.noop),
    ]
