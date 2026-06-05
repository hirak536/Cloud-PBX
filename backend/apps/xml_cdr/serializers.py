from rest_framework import serializers
from apps.client_api.serializers import ClientCDRSerializer
from .models import XmlCdr


class XmlCdrSerializer(serializers.ModelSerializer):
    domain_name = serializers.CharField(source='domain.domain_name', read_only=True)
    tenant_code = serializers.CharField(source='tenant.tenant_code', read_only=True)
    status = serializers.SerializerMethodField()

    def get_status(self, obj):
        # Reuse the client status logic, forwarding context (vm_route_idents) so a
        # missed call to a VM-routed extension is reported as voicemail here too.
        return ClientCDRSerializer(context=self.context).get_status(obj)

    class Meta:
        model = XmlCdr
        fields = '__all__'
        read_only_fields = ['xml_cdr_uuid', 'insert_date']
