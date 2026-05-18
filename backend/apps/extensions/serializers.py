from rest_framework import serializers
from .models import Extension, ExtensionUser


class ExtensionListSerializer(serializers.ModelSerializer):
    domain_name = serializers.CharField(source='domain.domain_name', read_only=True)
    tenant_code = serializers.CharField(source='tenant.tenant_code', read_only=True)

    class Meta:
        model = Extension
        fields = ['extension_uuid', 'extension', 'number_alias', 'effective_caller_id_name',
                  'effective_caller_id_number', 'voicemail_enabled', 'enabled', 'description',
                  'sip_username', 'password', 'domain_name', 'tenant_code']


class ExtensionSerializer(serializers.ModelSerializer):
    domain_name = serializers.CharField(source='domain.domain_name', read_only=True)
    tenant_code = serializers.CharField(source='tenant.tenant_code', read_only=True)
    outbound_did_number = serializers.CharField(source='outbound_did.destination_number', read_only=True, default=None)
    outbound_did_name = serializers.CharField(source='outbound_did.destination_name', read_only=True, default=None)

    class Meta:
        model = Extension
        fields = '__all__'
        read_only_fields = ['extension_uuid', 'insert_date', 'update_date']
        # Suppress the auto-generated UniqueTogetherValidator for (tenant, extension).
        # DRF requires all fields in the constraint to be present, even nullable ones.
        # Uniqueness is checked manually in validate() below.
        validators = []

    def validate(self, data):
        from apps.common.extension_conflict import check_extension_conflict
        tenant = (data.get('tenant')
                  or getattr(self.instance, 'tenant', None)
                  or self.context.get('tenant'))
        extension = data.get('extension', getattr(self.instance, 'extension', None))
        qs = Extension.objects.filter(tenant=tenant, extension=extension)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError({'extension': 'Extension already exists in this tenant.'})
        conflicts = check_extension_conflict(extension, tenant, exclude_model=Extension)
        if conflicts:
            raise serializers.ValidationError({'extension': conflicts[0]})
        # Sync effective caller ID from outbound caller ID only when the effective
        # fields are not explicitly provided in this request.
        outbound_number = data.get('outbound_caller_id_number',
                                   getattr(self.instance, 'outbound_caller_id_number', ''))
        outbound_name = data.get('outbound_caller_id_name',
                                 getattr(self.instance, 'outbound_caller_id_name', ''))
        if outbound_number and 'effective_caller_id_number' not in data:
            data['effective_caller_id_number'] = outbound_number
        if outbound_name and 'effective_caller_id_name' not in data:
            data['effective_caller_id_name'] = outbound_name
        return data


class ExtensionUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExtensionUser
        fields = '__all__'
        read_only_fields = ['extension_user_uuid', 'insert_date']
