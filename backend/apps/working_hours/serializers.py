from datetime import time
from rest_framework import serializers
from .models import WorkingHours, WorkingHoursDay, WorkingHoursHoliday


class _CloseTimeField(serializers.TimeField):
    """Accept "24:00" / "24:00:00" from the frontend (end-of-day slot) and
    normalize it to 23:59:59 before Django's TimeField validation runs."""

    def to_internal_value(self, value):
        if isinstance(value, str) and value.startswith('24:'):
            return time(23, 59, 59)
        return super().to_internal_value(value)


class WorkingHoursDaySerializer(serializers.ModelSerializer):
    close_time = _CloseTimeField(required=False, allow_null=True)

    class Meta:
        model = WorkingHoursDay
        fields = '__all__'
        read_only_fields = ['day_uuid', 'working_hours']


class WorkingHoursHolidaySerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkingHoursHoliday
        fields = '__all__'
        read_only_fields = ['holiday_uuid']


class WorkingHoursSerializer(serializers.ModelSerializer):
    days = WorkingHoursDaySerializer(many=True, required=False)
    holidays = WorkingHoursHolidaySerializer(many=True, read_only=True)

    class Meta:
        model = WorkingHours
        fields = '__all__'
        read_only_fields = [
            'working_hours_uuid',
            'insert_date', 'insert_user',
            'update_date', 'update_user',
        ]

    def _save_days(self, instance, days_data):
        instance.days.all().delete()
        for day_data in days_data:
            day_data.pop('day_uuid', None)
            day_data.pop('working_hours', None)
            WorkingHoursDay.objects.create(working_hours=instance, **day_data)

    def create(self, validated_data):
        days_data = validated_data.pop('days', [])
        instance = super().create(validated_data)
        self._save_days(instance, days_data)
        return instance

    def update(self, instance, validated_data):
        days_data = validated_data.pop('days', None)
        instance = super().update(instance, validated_data)
        if days_data is not None:
            self._save_days(instance, days_data)
        return instance


class WorkingHoursListSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkingHours
        fields = [
            'working_hours_uuid',
            'working_hours_name',
            'dialplan_extension',
            'working_hours_enabled',
            'open_dest_type',
            'closed_dest_type',
            'timezone',
        ]
