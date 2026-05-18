from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('destinations', '0007_destination_actions'),
    ]

    operations = [
        migrations.AddField(
            model_name='destination',
            name='callback_to_last_caller',
            field=models.BooleanField(default=False, help_text="If enabled, route the inbound call to the last extension that called this caller's number."),
        ),
    ]
