from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('working_hours', '0001_initial'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='workinghoursday',
            unique_together=set(),
        ),
        migrations.AlterModelOptions(
            name='workinghoursday',
            options={'ordering': ['day_of_week', 'open_time']},
        ),
    ]
