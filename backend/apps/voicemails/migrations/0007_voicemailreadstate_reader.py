from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('voicemails', '0006_voicemail_greeting_tts'),
    ]

    operations = [
        # Drop the old primary key and recreate with composite unique_together
        migrations.RunSQL(
            sql=[
                "ALTER TABLE voicemail_read_state ADD COLUMN reader VARCHAR(20) NOT NULL DEFAULT 'admin';",
                "ALTER TABLE voicemail_read_state DROP CONSTRAINT IF EXISTS voicemail_read_state_pkey;",
                "ALTER TABLE voicemail_read_state ADD COLUMN id SERIAL PRIMARY KEY;",
                "ALTER TABLE voicemail_read_state ADD CONSTRAINT voicemail_read_state_uuid_reader_uniq UNIQUE (message_uuid, reader);",
            ],
            reverse_sql=[
                "ALTER TABLE voicemail_read_state DROP CONSTRAINT IF EXISTS voicemail_read_state_uuid_reader_uniq;",
                "ALTER TABLE voicemail_read_state DROP COLUMN IF EXISTS id;",
                "ALTER TABLE voicemail_read_state DROP COLUMN IF EXISTS reader;",
                "ALTER TABLE voicemail_read_state ADD PRIMARY KEY (message_uuid);",
            ],
        ),
        migrations.AlterField(
            model_name='voicemailreadstate',
            name='message_uuid',
            field=models.CharField(max_length=255),
        ),
        migrations.AddField(
            model_name='voicemailreadstate',
            name='reader',
            field=models.CharField(default='admin', max_length=20),
        ),
        migrations.AlterUniqueTogether(
            name='voicemailreadstate',
            unique_together={('message_uuid', 'reader')},
        ),
    ]
