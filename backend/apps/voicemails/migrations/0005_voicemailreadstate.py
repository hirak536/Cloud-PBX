from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('voicemails', '0004_remove_voicemailmessage_caller_id_name_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='VoicemailReadState',
            fields=[
                ('message_uuid', models.CharField(max_length=255, primary_key=True, serialize=False)),
                ('is_read', models.BooleanField(default=False)),
                ('read_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'db_table': 'voicemail_read_state',
            },
        ),
    ]
