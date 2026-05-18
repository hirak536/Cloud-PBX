from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('xml_cdr', '0003_add_extension_number'),
    ]

    operations = [
        migrations.AddField(
            model_name='xmlcdr',
            name='bypass_media',
            field=models.BooleanField(default=False),
        ),
    ]
