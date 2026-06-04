from django.db import migrations


def backfill_station_id(apps, schema_editor):
    """Populate fax_file_station_id on existing rows where it's blank.

    Both directions use the stored caller ID number:
      - outbound: the sender's caller ID (our number)
      - inbound:  the caller's number (the sender)
    Rows with no caller ID number are left blank (nothing to derive).
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
        ('fax', '0007_faxfile_caller_id_name_station_id'),
    ]

    operations = [
        migrations.RunPython(backfill_station_id, noop_reverse),
    ]
