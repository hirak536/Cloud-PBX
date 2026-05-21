from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ivr_menus', '0003_ivrmenu_ivr_menu_allow_custom_codes_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='ivrmenu',
            name='ivr_menu_internal_dial_invalid_type',
            field=models.CharField(blank=True, default='', max_length=32),
        ),
        migrations.AddField(
            model_name='ivrmenu',
            name='ivr_menu_internal_dial_invalid_target_uuid',
            field=models.UUIDField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='ivrmenu',
            name='ivr_menu_internal_dial_invalid_external_number',
            field=models.CharField(blank=True, default='', max_length=64),
        ),
    ]
