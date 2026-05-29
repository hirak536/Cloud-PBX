from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='PeerStateHistory',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('extension', models.CharField(db_index=True, max_length=64)),
                ('tenant_code', models.CharField(blank=True, db_index=True, default='', max_length=64)),
                ('state', models.CharField(
                    choices=[
                        ('offline', 'Offline'),
                        ('available', 'Available'),
                        ('ringing', 'Ringing'),
                        ('inuse', 'In use'),
                        ('ringinuse', 'Ring in use'),
                        ('unknown', 'Unknown'),
                    ],
                    max_length=16,
                )),
                ('started_at', models.DateTimeField(db_index=True)),
                ('ended_at', models.DateTimeField(blank=True, db_index=True, null=True)),
            ],
            options={
                'db_table': 'esl_peer_state_history',
                'ordering': ['-started_at'],
                'indexes': [
                    models.Index(fields=['extension', 'started_at'], name='esl_psh_ext_start_idx'),
                    models.Index(fields=['extension', 'ended_at'], name='esl_psh_ext_end_idx'),
                ],
            },
        ),
    ]
