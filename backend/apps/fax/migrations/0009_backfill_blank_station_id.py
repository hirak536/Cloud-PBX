from django.db import migrations


def backfill_station_id(apps, schema_editor):
    """Re-backfill fax_file_station_id for rows still blank after 0008.

    0008 ran once at deploy; rows created afterwards by an older in-memory
    version of the send/receive views (before station id was set at create
    time) can still be blank. Same derivation as 0008: use the stored caller
    ID number for either direction. Rows with no caller ID are left blank.
    """
    FaxFile = apps.get_model('fax', 'FaxFile')
    qs = (
        FaxFile.objects
        .filter(fax_file_station_id='')
        .exclude(fax_file_caller_id_number='')
        .exclude(fax_file_caller_id_number__isnull=True)
    )
    for ff in qs.iterator():
        ff.fax_file_station_id = ff.fax_file_caller_id_number
        ff.save(update_fields=['fax_file_station_id'])


def noop_reverse(apps, schema_editor):
    # Not reversible — we can't know which rows were originally blank.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('fax', '0008_backfill_faxfile_station_id'),
    ]

    operations = [
        migrations.RunPython(backfill_station_id, noop_reverse),
    ]
