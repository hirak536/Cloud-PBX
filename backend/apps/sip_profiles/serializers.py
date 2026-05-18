from rest_framework import serializers
from .models import SipProfile, SipProfileSetting, SipProfileDomain


class SipProfileSettingSerializer(serializers.ModelSerializer):
    class Meta:
        model = SipProfileSetting
        fields = '__all__'
        read_only_fields = ['sip_profile_setting_uuid', 'insert_date']


class SipProfileDomainSerializer(serializers.ModelSerializer):
    class Meta:
        model = SipProfileDomain
        fields = '__all__'
        read_only_fields = ['sip_profile_domain_uuid']


class SipProfileSerializer(serializers.ModelSerializer):
    settings = SipProfileSettingSerializer(many=True, read_only=True)
    domains = SipProfileDomainSerializer(many=True, read_only=True)

    class Meta:
        model = SipProfile
        fields = '__all__'
        read_only_fields = ['sip_profile_uuid', 'insert_date', 'update_date']
