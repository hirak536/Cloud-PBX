from rest_framework import serializers
from .models import ExtensionSetting

class ExtensionSettingSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExtensionSetting
        fields = '__all__'
        read_only_fields = ['extension_setting_uuid', 'insert_date', 'insert_user', 'update_date', 'update_user']
