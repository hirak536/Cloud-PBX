from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('voicemails', '0007_voicemailreadstate_reader'),
    ]

    operations = [
        migrations.CreateModel(
            name='VoicemailTranscript',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('message_uuid', models.CharField(db_index=True, max_length=255, unique=True)),
                ('transcript', models.TextField(blank=True, default='')),
                ('confidence', models.FloatField(blank=True, null=True)),
                ('status', models.CharField(
                    choices=[('pending', 'Pending'), ('done', 'Done'), ('failed', 'Failed')],
                    default='pending',
                    max_length=16,
                )),
                ('error', models.TextField(blank=True, default='')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'db_table': 'voicemail_transcripts',
            },
        ),
    ]
