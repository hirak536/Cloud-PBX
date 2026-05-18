from rest_framework import serializers
from .models import TimeCondition, TimeConditionRange

class TimeConditionRangeSerializer(serializers.ModelSerializer):
    class Meta:
        model = TimeConditionRange
        fields = '__all__'
        read_only_fields = ['time_condition_uuid', 'insert_date']

class TimeConditionSerializer(serializers.ModelSerializer):
    ranges = TimeConditionRangeSerializer(many=True, read_only=True)

    class Meta:
        model = TimeCondition
        fields = '__all__'
        read_only_fields = ['dialplan_uuid', 'insert_date', 'insert_user', 'update_date', 'update_user']

class TimeConditionListSerializer(serializers.ModelSerializer):
    class Meta:
        model = TimeCondition
        fields = ['dialplan_uuid', 'dialplan_name', 'dialplan_extension', 'dialplan_enabled']
