from rest_framework import serializers
from apps.client_api.serializers import ClientCDRSerializer
from .models import XmlCdr


class XmlCdrSerializer(serializers.ModelSerializer):
    # Read from the denormalized columns (no FK join) so this works once CDRs
    # live in a separate DB. The fields are plain model fields now, so they're
    # serialized automatically via fields='__all__'; no source= needed.
    status = serializers.SerializerMethodField()

    def get_status(self, obj):
        # Reuse the client status logic, forwarding context (vm_route_idents) so a
        # missed call to a VM-routed extension is reported as voicemail here too.
        return ClientCDRSerializer(context=self.context).get_status(obj)

    class Meta:
        model = XmlCdr
        fields = '__all__'
        read_only_fields = ['xml_cdr_uuid', 'insert_date']
