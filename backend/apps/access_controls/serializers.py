from rest_framework import serializers
from .models import AccessControl, AccessControlNode

class AccessControlNodeSerializer(serializers.ModelSerializer):
    class Meta:
        model = AccessControlNode
        fields = '__all__'
        read_only_fields = ['access_control_node_uuid', 'insert_date', 'insert_user']

class AccessControlSerializer(serializers.ModelSerializer):
    nodes = AccessControlNodeSerializer(many=True, read_only=True)

    class Meta:
        model = AccessControl
        fields = '__all__'
        read_only_fields = ['access_control_uuid', 'insert_date', 'insert_user', 'update_date', 'update_user']

class AccessControlListSerializer(serializers.ModelSerializer):
    node_count = serializers.SerializerMethodField()

    class Meta:
        model = AccessControl
        fields = ['access_control_uuid', 'access_control_name', 'access_control_default', 'node_count']

    def get_node_count(self, obj):
        return obj.nodes.count()
