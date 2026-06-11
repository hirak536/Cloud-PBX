"""
Migration 0010 — widen v_xml_cdr.last_arg to varchar(1024) via raw SQL.

Migration 0008 used AlterField to set last_arg max_length=1024, but v_xml_cdr is
a FusionPBX-owned table and that AlterField did not actually change the column —
the real column stayed varchar(256). Voicemail legs store the full record-stop
curl (~400+ chars) in last_arg, so the over-length value made the ENTIRE CDR row
insert fail; the call was left as a stale synthetic USER_BUSY row instead of
being classified as "Went to Voicemail".

This migration applies the widen explicitly so a rebuilt environment is correct.
Idempotent: only alters when the column is still narrower than 1024, and the
reverse is a no-op (we never want to shrink it back and re-introduce the bug).
"""
from django.db import migrations


WIDEN_SQL = """
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'v_xml_cdr'
          AND column_name = 'last_arg'
          AND (character_maximum_length IS NULL OR character_maximum_length < 1024)
    ) THEN
        ALTER TABLE v_xml_cdr ALTER COLUMN last_arg TYPE varchar(1024);
    END IF;
END $$;
"""


class Migration(migrations.Migration):

    dependencies = [
        ('xml_cdr', '0009_unique_call_uuid_leg'),
    ]

    operations = [
        migrations.RunSQL(sql=WIDEN_SQL, reverse_sql=migrations.RunSQL.noop),
    ]
