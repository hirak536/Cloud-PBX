from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('extensions', '0012_merge'),
    ]

    operations = [
        migrations.AddField(
            model_name='extension',
            name='reject_to_voicemail',
            field=models.BooleanField(
                default=False,
                help_text='Immediately route to voicemail when any registered device rejects the call.'
            ),
        ),
    ]
