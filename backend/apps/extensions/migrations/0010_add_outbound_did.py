import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('destinations', '0001_initial'),
        ('extensions', '0009_alter_extension_sip_bypass_media'),
    ]

    operations = [
        migrations.AddField(
            model_name='extension',
            name='outbound_did',
            field=models.ForeignKey(
                blank=True,
                db_column='outbound_did_uuid',
                help_text='DID whose number is used as the outbound caller ID for this extension.',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='outbound_extensions',
                to='destinations.destination',
                verbose_name='Outbound caller ID (DID)',
            ),
        ),
    ]
