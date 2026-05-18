from django.db import migrations, models


def migrate_greeting_choices(apps, schema_editor):
    Voicemail = apps.get_model('voicemails', 'Voicemail')
    Voicemail.objects.filter(voicemail_greeting='auto_no_instructions').update(
        voicemail_greeting='auto_with_instructions'
    )
    Voicemail.objects.filter(voicemail_greeting='recorded').update(
        voicemail_greeting='recorded_name'
    )


class Migration(migrations.Migration):

    dependencies = [
        ('voicemails', '0005_voicemailreadstate'),
    ]

    operations = [
        migrations.AddField(
            model_name='voicemail',
            name='tts_greeting_text',
            field=models.CharField(
                blank=True, default='', max_length=512,
                verbose_name='TTS greeting text',
                help_text='Custom text for TTS greeting. Leave blank for default.',
            ),
        ),
        migrations.RunPython(migrate_greeting_choices, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='voicemail',
            name='voicemail_greeting',
            field=models.CharField(
                blank=True,
                choices=[
                    ('auto_with_instructions', 'Automatic with Instructions'),
                    ('tts_name', 'Text-to-Speech Greeting'),
                    ('recorded_name', 'Recorded Name Greeting'),
                ],
                default='auto_with_instructions',
                max_length=32,
                verbose_name='Greeting style',
            ),
        ),
    ]
