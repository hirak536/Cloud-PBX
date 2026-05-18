from django.db.models import Count, Sum, Avg, Q
from rest_framework import serializers

from apps.destinations.models import Destination
from apps.extensions.models import Extension
from apps.fax.models import Fax, FaxFile
from apps.voicemails.models import VoicemailMessage, VoicemailReadState
from apps.xml_cdr.models import XmlCdr
from .models import TenantAPIKey


# ──────────────────────────────────────────────
# API Key management serializers (superuser UI)
# ──────────────────────────────────────────────

class TenantAPIKeyListSerializer(serializers.ModelSerializer):
    tenant_code = serializers.CharField(source='tenant.tenant_code', read_only=True)
    tenant_name = serializers.CharField(source='tenant.tenant_name', read_only=True)
    created_by_username = serializers.CharField(source='created_by.username', read_only=True, default=None)

    class Meta:
        model = TenantAPIKey
        fields = [
            'id', 'tenant', 'tenant_code', 'tenant_name',
            'label', 'created_by_username', 'created_at',
            'expires_at', 'is_active', 'webhook_url',
        ]
        read_only_fields = ['id', 'created_at']


class TenantAPIKeyCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = TenantAPIKey
        fields = ['tenant', 'label', 'expires_at', 'webhook_url', 'webhook_secret']

    def create(self, validated_data):
        request = self.context['request']
        instance, plaintext = TenantAPIKey.generate(
            tenant=validated_data['tenant'],
            label=validated_data['label'],
            created_by=request.user,
            expires_at=validated_data.get('expires_at'),
            webhook_url=validated_data.get('webhook_url', ''),
            webhook_secret=validated_data.get('webhook_secret', ''),
        )
        # Attach plaintext so the view can return it once
        instance._plaintext = plaintext
        return instance


class TenantAPIKeyUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = TenantAPIKey
        fields = ['label', 'expires_at', 'is_active', 'webhook_url', 'webhook_secret']


# ──────────────────────────────────────────────
# Client API serializers (read-only, tenant-scoped)
# ──────────────────────────────────────────────

class ClientTenantSerializer(serializers.Serializer):
    tenant_id = serializers.UUIDField(source='tenant_uuid')
    tenant_code = serializers.CharField()
    tenant_name = serializers.CharField()


class ClientExtensionSerializer(serializers.ModelSerializer):
    sip_username = serializers.CharField(read_only=True)
    sip_name = serializers.CharField(source='effective_caller_id_name', read_only=True)

    class Meta:
        model = Extension
        fields = [
            'extension_uuid', 'sip_username', 'sip_name', 'password', 'enabled',
        ]


class ClientDestinationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Destination
        fields = [
            'destination_uuid', 'destination_number', 'destination_name',
            'destination_enabled',
        ]


class ClientCDRSerializer(serializers.ModelSerializer):
    missed_call = serializers.BooleanField(read_only=True)
    status = serializers.SerializerMethodField()

    def get_status(self, obj):
        cause = (obj.hangup_cause or '').upper()

        # Voicemail — detect regardless of which last_app FreeSWITCH reports:
        #   - last_app=voicemail (standard)
        #   - last_app=speak + TTS arg (flite|kal|...) — greeting was last action
        #   - last_app=record + /voicemail/ path — recording was last action
        #   - last_app=phrase + voicemail_record_message — native FS phrase macro
        last_app = (obj.last_app or '').lower()
        last_arg = obj.last_arg or ''
        if last_app == 'voicemail':
            return 'WENT_TO_VOICEMAIL'
        if last_app == 'speak' and '|' in last_arg:
            return 'WENT_TO_VOICEMAIL'
        if last_app == 'record' and '/voicemail/' in last_arg:
            return 'WENT_TO_VOICEMAIL'
        if last_app == 'system' and 'voicemail-messages/ingest' in last_arg:
            return 'WENT_TO_VOICEMAIL'
        if last_app == 'phrase' and 'voicemail' in last_arg:
            return 'WENT_TO_VOICEMAIL'

        # Answered
        if cause in ('NORMAL_CLEARING', 'CALL_AWARDED_DELIVERED') and obj.billsec > 0:
            return 'ANSWERED'

        # Busy
        if cause == 'USER_BUSY':
            return 'BUSY'

        # Congestion
        if cause in ('NORMAL_CIRCUIT_CONGESTION', 'SWITCH_CONGESTION',
                     'RESOURCE_UNAVAILABLE', 'SERVICE_UNAVAILABLE'):
            return 'CONGESTION'

        # Not answered / offline — missed if flag set
        if cause in ('NO_ANSWER', 'NO_USER_RESPONSE', 'SUBSCRIBER_ABSENT', 'ALLOTTED_TIMEOUT',
                     'USER_NOT_REGISTERED', 'ORIGINATOR_CANCEL'):
            if obj.direction == 'outbound':
                return 'NO_ANSWER'
            if obj.missed_call:
                return 'MISSED'
            return 'NO_ANSWER'

        # Failed
        if cause in (
            'UNALLOCATED_NUMBER', 'NO_ROUTE_TRANSIT_NET', 'NO_ROUTE_DESTINATION',
            'CALL_REJECTED', 'NUMBER_CHANGED', 'DESTINATION_OUT_OF_ORDER',
            'INVALID_NUMBER_FORMAT', 'FACILITY_REJECTED', 'NETWORK_OUT_OF_ORDER',
            'TEMPORARY_FAILURE', 'CHANNEL_UNAVAILABLE', 'OUTGOING_CALL_BARRED',
            'INCOMING_CALL_BARRED', 'BEARER_NOT_AUTHORIZED', 'BEARER_NOT_AVAILABLE',
            'BEARER_NOT_IMPLEMENTED', 'FACILITY_NOT_IMPLEMENTED', 'SERVICE_NOT_IMPLEMENTED',
            'INVALID_CALL_REFERENCE', 'INCOMPATIBLE_DESTINATION', 'INTERWORKING',
            'CRASH', 'SYSTEM_SHUTDOWN', 'LOSE_RACE', 'MANAGER_REQUEST',
            'USER_CHALLENGE', 'MEDIA_TIMEOUT', 'PICKED_OFF',
            'PROGRESS_TIMEOUT', 'GATEWAY_DOWN',
        ):
            return 'FAILED'

        # Fallback
        if obj.billsec > 0:
            return 'ANSWERED'
        if obj.missed_call:
            return 'MISSED'
        return 'FAILED'

    class Meta:
        model = XmlCdr
        fields = [
            'xml_cdr_uuid', 'caller_id_number', 'caller_id_name',
            'destination_number', 'extension_number', 'direction',
            'start_stamp', 'answer_stamp', 'end_stamp',
            'duration', 'billsec', 'hangup_cause',
            'missed_call', 'status', 'record_path',
        ]


class ClientFaxSerializer(serializers.ModelSerializer):
    class Meta:
        model = Fax
        fields = [
            'fax_uuid', 'fax_name', 'fax_extension', 'fax_email',
            'fax_caller_id_name', 'fax_caller_id_number', 'fax_enabled',
        ]


class ClientFaxFileSerializer(serializers.ModelSerializer):
    fax_caller_id_name = serializers.CharField(source='fax_file_caller_id_name', read_only=True)
    fax_caller_id_number = serializers.CharField(source='fax_file_caller_id_number', read_only=True)
    fax_destination_number = serializers.CharField(source='fax_file_destination_number', read_only=True)
    fax_station_id = serializers.CharField(source='fax_file_station_id', read_only=True)
    direction = serializers.CharField(read_only=True)
    download_url = serializers.SerializerMethodField()

    class Meta:
        model = FaxFile
        fields = [
            'fax_file_uuid', 'fax', 'fax_file_status', 'direction', 'fax_file_pages',
            'fax_file_name', 'fax_caller_id_name', 'fax_caller_id_number',
            'fax_destination_number', 'fax_station_id',
            'retry_count', 'insert_date', 'file_size_bytes', 'download_url',
        ]

    def get_download_url(self, obj):
        request = self.context.get('request')
        tenant_uuid = self.context.get('tenant_uuid')
        if not request or not tenant_uuid:
            return None
        from django.urls import reverse
        return request.build_absolute_uri(
            reverse('client-fax-file-download', kwargs={
                'tenant_uuid': str(tenant_uuid),
                'fax_file_uuid': str(obj.fax_file_uuid),
            })
        )


class ClientVoicemailMessageSerializer(serializers.ModelSerializer):
    caller_id_number = serializers.CharField(source='cid_number', read_only=True)
    caller_id_name = serializers.CharField(source='cid_name', read_only=True)
    message_length = serializers.IntegerField(source='message_len', read_only=True)
    read = serializers.SerializerMethodField()
    created_epoch = serializers.IntegerField(read_only=True)
    audio_url = serializers.SerializerMethodField()
    transcript = serializers.SerializerMethodField()

    class Meta:
        model = VoicemailMessage
        fields = [
            'uuid', 'caller_id_number', 'caller_id_name',
            'message_length', 'created_epoch', 'read', 'audio_url', 'transcript',
        ]

    def get_read(self, obj):
        read_uuids = self.context.get('read_uuids', set())
        return obj.uuid in read_uuids

    def get_audio_url(self, obj):
        request = self.context.get('request')
        tenant_uuid = self.context.get('tenant_uuid')
        if not request or not tenant_uuid:
            return None
        from django.urls import reverse
        return request.build_absolute_uri(
            reverse('client-voicemail-audio', kwargs={
                'tenant_uuid': str(tenant_uuid),
                'message_uuid': obj.uuid,
            })
        )

    def get_transcript(self, obj):
        from apps.voicemails.models import VoicemailTranscript  # noqa: PLC0415
        try:
            t = VoicemailTranscript.objects.get(message_uuid=obj.uuid)
            if t.status == VoicemailTranscript.STATUS_DONE:
                return t.transcript
            return 'not available'
        except VoicemailTranscript.DoesNotExist:
            return 'not available'

    # voicemail_id not on model directly; injected by view via context
    def to_representation(self, instance):
        data = super().to_representation(instance)
        data['voicemail_id'] = self.context.get('voicemail_map', {}).get(
            f'{instance.username}@{instance.domain}', instance.username
        )
        return data
