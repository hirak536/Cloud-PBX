from rest_framework import serializers
from .models import Fax, FaxFile

class FaxFileSerializer(serializers.ModelSerializer):
    fax_name = serializers.SerializerMethodField()
    fax_caller_id_name = serializers.SerializerMethodField()
    fax_caller_id_number = serializers.SerializerMethodField()

    def get_fax_name(self, obj):
        return obj.fax.fax_name if obj.fax else obj.fax_file_name

    def get_fax_caller_id_name(self, obj):
        return obj.fax.fax_caller_id_name if obj.fax else obj.fax_file_caller_id_number

    def get_fax_caller_id_number(self, obj):
        return obj.fax.fax_caller_id_number if obj.fax else obj.fax_file_caller_id_number

    class Meta:
        model = FaxFile
        fields = '__all__'
        read_only_fields = ['fax_file_uuid', 'insert_date', 'fax_name', 'fax_caller_id_name', 'fax_caller_id_number']

class FaxSerializer(serializers.ModelSerializer):
    files = FaxFileSerializer(many=True, read_only=True)

    class Meta:
        model = Fax
        fields = '__all__'
        read_only_fields = ['fax_uuid', 'insert_date', 'insert_user', 'update_date', 'update_user']
        extra_kwargs = {
            # Never expose the stored FTP password in API responses. It can be
            # written (set/updated) but is omitted from serialized output.
            'fax_ftp_password': {'write_only': True, 'required': False},
        }

class FaxListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Fax
        fields = ['fax_uuid', 'fax_name', 'fax_extension', 'fax_email', 'fax_enabled',
                  'fax_caller_id_name', 'fax_caller_id_number', 'fax_forward_number', 'fax_description']
