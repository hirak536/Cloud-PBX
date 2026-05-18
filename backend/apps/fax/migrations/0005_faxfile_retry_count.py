from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('fax', '0004_alter_faxfile_fax'),
    ]

    operations = [
        migrations.AddField(
            model_name='faxfile',
            name='retry_count',
            field=models.IntegerField(default=0),
        ),
    ]
