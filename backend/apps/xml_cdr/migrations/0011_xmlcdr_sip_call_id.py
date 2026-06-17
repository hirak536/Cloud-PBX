from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('xml_cdr', '0010_widen_last_arg_sql'),
    ]

    operations = [
        migrations.AddField(
            model_name='xmlcdr',
            name='sip_call_id',
            field=models.CharField(blank=True, db_index=True, default='', max_length=256),
        ),
    ]
