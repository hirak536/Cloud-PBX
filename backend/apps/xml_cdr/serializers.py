from rest_framework import serializers
from apps.client_api.serializers import ClientCDRSerializer
from .models import XmlCdr


class XmlCdrSerializer(serializers.ModelSerializer):
    domain_name = serializers.CharField(source='domain.domain_name', read_only=True)
    tenant_code = serializers.CharField(source='tenant.tenant_code', read_only=True)
    status = serializers.SerializerMethodField()

    def get_status(self, obj):
        return ClientCDRSerializer.get_status(ClientCDRSerializer(), obj)

    class Meta:
        model = XmlCdr
        fields = '__all__'
        read_only_fields = ['xml_cdr_uuid', 'insert_date']
