from rest_framework import serializers
from .models import Voicemail, VoicemailMessage, VoicemailOption, VoicemailReadState


class VoicemailMessageSerializer(serializers.ModelSerializer):
    is_read = serializers.SerializerMethodField()
    duration_seconds = serializers.IntegerField(source='message_len', read_only=True)
    mailbox_name = serializers.SerializerMethodField()

    class Meta:
        model = VoicemailMessage
        fields = [
            'uuid', 'username', 'mailbox_name', 'domain',
            'cid_name', 'cid_number',
            'in_folder', 'file_path',
            'message_len', 'duration_seconds',
            'flags', 'read_flags', 'forwarded_by',
            'created_epoch', 'read_epoch',
            'is_read',
        ]
        read_only_fields = ['uuid', 'created_epoch', 'file_path']

    def get_is_read(self, obj):
        read_uuids = self.context.get('read_uuids', set())
        return (obj.uuid in read_uuids) or (obj.read_flags == 'read')

    def get_mailbox_name(self, obj):
        # Resolve voicemail UUID → voicemail_id (extension number)
        uuid_map = self.context.get('uuid_to_voicemail_id')
        if uuid_map:
            return uuid_map.get(obj.username, obj.username)
        try:
            vm = Voicemail.objects.get(voicemail_uuid=obj.username)
            return vm.voicemail_id
        except Voicemail.DoesNotExist:
            return obj.username


class VoicemailOptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = VoicemailOption
        fields = '__all__'
        read_only_fields = ['voicemail_option_uuid']


class VoicemailSerializer(serializers.ModelSerializer):
    options = VoicemailOptionSerializer(many=True, read_only=True)
    domain_name = serializers.CharField(source='domain.domain_name', read_only=True)
    tenant_code = serializers.CharField(source='tenant.tenant_code', read_only=True)
    greeting_recording_name = serializers.CharField(
        source='voicemail_greeting_recording.recording_name', read_only=True, default=None)
    greeting_recording_filename = serializers.CharField(
        source='voicemail_greeting_recording.recording_filename', read_only=True, default=None)

    class Meta:
        model = Voicemail
        fields = '__all__'
        read_only_fields = ['voicemail_uuid', 'insert_date', 'update_date']
