from rest_framework import serializers
from .models import SofiaGlobalSetting


class SofiaGlobalSettingSerializer(serializers.ModelSerializer):
    class Meta:
        model = SofiaGlobalSetting
        fields = '__all__'
        read_only_fields = ['sofia_global_setting_uuid', 'insert_date', 'update_date']
