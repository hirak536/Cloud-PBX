from rest_framework import serializers
from .models import Conference, ConferenceProfile, ConferenceProfileSetting, ConferenceCenter


class ConferenceProfileSettingSerializer(serializers.ModelSerializer):
    class Meta:
        model = ConferenceProfileSetting
        fields = '__all__'
        read_only_fields = ['conference_profile_setting_uuid']


class ConferenceProfileSerializer(serializers.ModelSerializer):
    settings = ConferenceProfileSettingSerializer(many=True, read_only=True)

    class Meta:
        model = ConferenceProfile
        fields = '__all__'
        read_only_fields = ['conference_profile_uuid', 'insert_date']


class ConferenceSerializer(serializers.ModelSerializer):
    domain_name = serializers.CharField(source='domain.domain_name', read_only=True)
    tenant_code = serializers.CharField(source='tenant.tenant_code', read_only=True)
    profile_name = serializers.CharField(source='conference_profile.conference_profile_name', read_only=True)

    class Meta:
        model = Conference
        fields = '__all__'
        read_only_fields = ['conference_uuid', 'domain', 'tenant', 'insert_date', 'update_date']
        extra_kwargs = {'conference_pin': {'write_only': True}}


class ConferenceCenterSerializer(serializers.ModelSerializer):
    class Meta:
        model = ConferenceCenter
        fields = '__all__'
        read_only_fields = ['conference_center_uuid', 'domain', 'tenant']
