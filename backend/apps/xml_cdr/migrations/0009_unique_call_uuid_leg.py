"""
Migration 0009 — unique_call_uuid_leg

1. Delete duplicate (call_uuid, leg) rows, keeping the row with the longest
   billsec (ties broken by earliest insert_date so the original survives).
2. Add a partial unique constraint on (call_uuid, leg) WHERE call_uuid IS NOT NULL.

atomic=False so each step runs in its own transaction — required because the
v_xml_cdr table has a trigger that prevents CREATE INDEX inside a transaction
that already modified rows in that table.
"""
from django.db import migrations, models, transaction


def remove_duplicates(apps, schema_editor):
    """
    For every (call_uuid, leg) group with more than one row, delete all but the
    keeper.  Keeper = highest billsec; tie → earliest insert_date; tie → lowest PK.
    """
    db = schema_editor.connection.alias
    XmlCdr = apps.get_model('xml_cdr', 'XmlCdr')

    from django.db.models import Count
    dup_groups = list(
        XmlCdr.objects.using(db)
        .exclude(call_uuid=None)
        .values('call_uuid', 'leg')
        .annotate(cnt=Count('xml_cdr_uuid'))
        .filter(cnt__gt=1)
    )

    deleted_total = 0
    for group in dup_groups:
        rows = list(
            XmlCdr.objects.using(db)
            .filter(call_uuid=group['call_uuid'], leg=group['leg'])
            .order_by('-billsec', 'insert_date', 'xml_cdr_uuid')
            .values_list('xml_cdr_uuid', flat=True)
        )
        to_delete = rows[1:]
        with transaction.atomic(using=db):
            deleted, _ = XmlCdr.objects.using(db).filter(xml_cdr_uuid__in=to_delete).delete()
            deleted_total += deleted

    if deleted_total:
        print(f'\n  Removed {deleted_total} duplicate CDR rows.')


class Migration(migrations.Migration):
    # Must be non-atomic: the trigger on v_xml_cdr prevents CREATE INDEX inside
    # a transaction that already deleted rows from the same table.
    atomic = False

    dependencies = [
        ('xml_cdr', '0008_alter_xmlcdr_last_arg'),
    ]

    operations = [
        # Step 1: purge duplicates (each group in its own transaction via atomic=False + explicit atomic()).
        migrations.RunPython(remove_duplicates, migrations.RunPython.noop),

        # Step 2: add the partial unique constraint in a fresh transaction.
        migrations.AddConstraint(
            model_name='xmlcdr',
            constraint=models.UniqueConstraint(
                fields=['call_uuid', 'leg'],
                condition=models.Q(call_uuid__isnull=False),
                name='unique_call_uuid_leg',
            ),
        ),
    ]
