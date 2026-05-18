from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('custom_destinations', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='customdestination',
            name='callback_to_last_caller',
            field=models.BooleanField(
                default=False,
                help_text="Route inbound calls to the last extension that previously called the caller's number.",
            ),
        ),
    ]
