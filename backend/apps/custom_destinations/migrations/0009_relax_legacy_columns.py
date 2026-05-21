"""
Relax legacy NOT NULL columns on v_custom_destinations.

The table predates the Django model and carries columns the app doesn't manage
(caller_id_*, else_dest_*, if_dest_*, template_type). They were declared NOT
NULL with no default, so Django INSERTs blew up. We give them empty-string
defaults and let them stay NOT NULL — same semantics as a Django CharField with
blank=True default=''.

Future plan: if/when the model adopts these columns explicitly, this migration
becomes a no-op.
"""
from django.db import migrations


LEGACY_DEFAULTS = [
    ('caller_id_name',            ''),
    ('caller_id_name_type',       ''),
    ('caller_id_number',          ''),
    ('caller_id_number_type',     ''),
    ('else_dest_external_number', ''),
    ('if_dest_external_number',   ''),
    ('template_type',             ''),
]


def forwards(apps, schema_editor):
    with schema_editor.connection.cursor() as c:
        for col, default in LEGACY_DEFAULTS:
            # Backfill existing NULLs (safe even though they're NOT NULL — covers any
            # historical rows inserted via raw SQL paths).
            c.execute(f"UPDATE v_custom_destinations SET {col} = %s WHERE {col} IS NULL", [default])
            # Apply a DB-level default so future Django INSERTs that omit the column succeed.
            c.execute(f"ALTER TABLE v_custom_destinations ALTER COLUMN {col} SET DEFAULT %s", [default])


def backwards(apps, schema_editor):
    with schema_editor.connection.cursor() as c:
        for col, _ in LEGACY_DEFAULTS:
            c.execute(f"ALTER TABLE v_custom_destinations ALTER COLUMN {col} DROP DEFAULT")


class Migration(migrations.Migration):

    dependencies = [
        ('custom_destinations', '0008_backfill_kind_from_callback'),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
