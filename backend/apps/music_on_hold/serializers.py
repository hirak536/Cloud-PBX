from rest_framework import serializers
from .models import MusicOnHold

class MusicOnHoldSerializer(serializers.ModelSerializer):
    class Meta:
        model = MusicOnHold
        fields = '__all__'
        read_only_fields = ['music_on_hold_uuid', 'insert_date', 'insert_user', 'update_date', 'update_user']
