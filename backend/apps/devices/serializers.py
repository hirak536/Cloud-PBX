from rest_framework import serializers
from .models import Device, DeviceLine, DeviceSetting

class DeviceLineSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeviceLine
        fields = '__all__'
        read_only_fields = ['device_line_uuid', 'insert_date', 'insert_user']

class DeviceSettingSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeviceSetting
        fields = '__all__'
        read_only_fields = ['device_setting_uuid']

class DeviceSerializer(serializers.ModelSerializer):
    lines = DeviceLineSerializer(many=True, read_only=True)
    settings = DeviceSettingSerializer(many=True, read_only=True)

    class Meta:
        model = Device
        fields = '__all__'
        read_only_fields = ['device_uuid', 'insert_date', 'insert_user', 'update_date', 'update_user']

class DeviceListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Device
        fields = ['device_uuid', 'device_mac_address', 'device_label', 'device_vendor', 'device_model', 'device_enabled']
