from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('xml_cdr', '0002_add_tenant'),
    ]

    operations = [
        migrations.AddField(
            model_name='xmlcdr',
            name='extension_number',
            field=models.CharField(blank=True, default='', max_length=32),
        ),
    ]
