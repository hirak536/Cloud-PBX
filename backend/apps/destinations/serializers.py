import uuid as _uuid
from collections import defaultdict
from rest_framework import serializers
from .models import Destination, DestinationAction
from apps.fax.models import Fax


def _build_label_map(all_actions, tenant):
    """
    Batch-fetch labels for a flat list of DestinationAction instances.
    Returns {(dest_type, uuid): label_str}.
    """
    by_type = defaultdict(list)
    for a in all_actions:
        if a.dest_type and a.dest_target_uuid:
            by_type[a.dest_type].append(a.dest_target_uuid)

    labels = {}

    try:
        if by_type.get('extension'):
            from apps.extensions.models import Extension
            for e in Extension.objects.filter(extension_uuid__in=by_type['extension'], tenant=tenant).values('extension_uuid', 'extension', 'effective_caller_id_name'):
                label = f"{e['extension']} — {e['effective_caller_id_name']}" if e['effective_caller_id_name'] else e['extension']
                labels[('extension', e['extension_uuid'])] = label

        if by_type.get('voicemail'):
            from apps.voicemails.models import Voicemail
            for v in Voicemail.objects.filter(voicemail_uuid__in=by_type['voicemail'], tenant=tenant).values('voicemail_uuid', 'voicemail_id'):
                labels[('voicemail', v['voicemail_uuid'])] = f"Voicemail {v['voicemail_id']}"

        if by_type.get('ivr_menu'):
            from apps.ivr_menus.models import IvrMenu
            for i in IvrMenu.objects.filter(ivr_menu_uuid__in=by_type['ivr_menu'], tenant=tenant).values('ivr_menu_uuid', 'ivr_menu_name'):
                labels[('ivr_menu', i['ivr_menu_uuid'])] = i['ivr_menu_name']

        if by_type.get('ring_group'):
            from apps.ring_groups.models import RingGroup
            for r in RingGroup.objects.filter(ring_group_uuid__in=by_type['ring_group'], tenant=tenant).values('ring_group_uuid', 'ring_group_name'):
                labels[('ring_group', r['ring_group_uuid'])] = r['ring_group_name']

        if by_type.get('working_hours'):
            from apps.working_hours.models import WorkingHours
            for w in WorkingHours.objects.filter(working_hours_uuid__in=by_type['working_hours'], tenant=tenant).values('working_hours_uuid', 'working_hours_name'):
                labels[('working_hours', w['working_hours_uuid'])] = w['working_hours_name']

        if by_type.get('custom_destination'):
            from apps.custom_destinations.models import CustomDestination
            for cd in CustomDestination.objects.filter(custom_destination_uuid__in=by_type['custom_destination'], tenant=tenant).values('custom_destination_uuid', 'name'):
                labels[('custom_destination', cd['custom_destination_uuid'])] = cd['name']
    except Exception:
        pass

    return labels


def _apply_labels(actions_data, label_map):
    """Annotate serialized action dicts with dest_label in-place."""
    for action in actions_data:
        dtype = action.get('dest_type')
        duuid = action.get('dest_target_uuid')
        if dtype == 'hangup':
            action['dest_label'] = 'Hangup'
        elif dtype in ('external', 'number'):
            action['dest_label'] = action.get('dest_external_number') or None
        elif dtype and duuid:
            try:
                key = (dtype, _uuid.UUID(str(duuid)))
            except (ValueError, AttributeError):
                key = (dtype, duuid)
            action['dest_label'] = label_map.get(key)
        else:
            action['dest_label'] = None


class DestinationListListSerializer(serializers.ListSerializer):
    """Custom list serializer that resolves dest_label with one batch of queries."""

    def to_representation(self, data):
        result = super().to_representation(data)
        tenant = self.context.get('tenant')
        if not tenant:
            return result

        # Collect all actions across all destinations in one pass
        all_actions = []
        for destination in data:
            all_actions.extend(destination.actions.all())

        label_map = _build_label_map(all_actions, tenant)

        for dest_data in result:
            _apply_labels(dest_data.get('actions', []), label_map)

        return result


class DestinationActionSerializer(serializers.ModelSerializer):
    dest_label = serializers.CharField(read_only=True, default=None)

    class Meta:
        model = DestinationAction
        fields = ['destination_action_uuid', 'dest_type', 'dest_target_uuid', 'dest_external_number', 'order', 'dest_label']
        read_only_fields = ['destination_action_uuid', 'dest_label']


class DestinationListSerializer(serializers.ModelSerializer):
    dest_type_display = serializers.CharField(source='get_dest_type_display', read_only=True)
    actions = DestinationActionSerializer(many=True, read_only=True)
    tenant_code = serializers.SerializerMethodField()

    def get_tenant_code(self, obj):
        if obj.tenant:
            return obj.tenant.tenant_code
        if obj.domain and obj.domain.tenant:
            return obj.domain.tenant.tenant_code
        return None

    class Meta:
        model = Destination
        list_serializer_class = DestinationListListSerializer
        fields = [
            'destination_uuid',
            'destination_name',
            'destination_number',
            'destination_number_regex',
            'dest_type',
            'dest_type_display',
            'fax_id',
            'actions',
            'destination_enabled',
            'destination_description',
            'tenant',
            'tenant_code',
        ]


class DestinationSerializer(serializers.ModelSerializer):
    dest_type_display = serializers.CharField(source='get_dest_type_display', read_only=True)
    actions = DestinationActionSerializer(many=True, required=False)
    fax_id = serializers.PrimaryKeyRelatedField(
        source='fax',
        queryset=Fax.objects.all(),
        allow_null=True,
        required=False,
    )

    class Meta:
        model = Destination
        fields = '__all__'
        read_only_fields = [
            'destination_uuid', 'insert_date', 'insert_user',
            'update_date', 'update_user', 'dest_type_display',
        ]

    def validate_destination_number(self, value):
        qs = Destination.objects.filter(destination_number=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError(
                f'DID {value} is already in use by another destination.'
            )
        return value

    def _sync_dest_type(self, validated_data, actions_data):
        """Keep dest_type/dest_target_uuid/dest_external_number in sync with the first action."""
        if actions_data:
            first = actions_data[0]
            validated_data['dest_type']           = first.get('dest_type', '')
            validated_data['dest_target_uuid']     = first.get('dest_target_uuid') or None
            validated_data['dest_external_number'] = first.get('dest_external_number', '')
        elif 'dest_type' not in validated_data:
            validated_data['dest_type'] = ''

    def _save_actions(self, destination, actions_data):
        destination.actions.all().delete()
        for i, action_data in enumerate(actions_data):
            action_data.pop('order', None)
            DestinationAction.objects.create(destination=destination, order=i, **action_data)

    def create(self, validated_data):
        actions_data = validated_data.pop('actions', [])
        self._sync_dest_type(validated_data, actions_data)
        destination = super().create(validated_data)
        self._save_actions(destination, actions_data)
        return destination

    def update(self, instance, validated_data):
        actions_data = validated_data.pop('actions', None)
        if actions_data is not None:
            self._sync_dest_type(validated_data, actions_data)
        instance = super().update(instance, validated_data)
        if actions_data is not None:
            self._save_actions(instance, actions_data)
        return instance
