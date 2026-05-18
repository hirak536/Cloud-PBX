from rest_framework import serializers
from .models import FollowMe, FollowMeDestination

class FollowMeDestinationSerializer(serializers.ModelSerializer):
    class Meta:
        model = FollowMeDestination
        fields = '__all__'
        read_only_fields = ['follow_me_destination_uuid', 'insert_date']

class FollowMeSerializer(serializers.ModelSerializer):
    destinations = FollowMeDestinationSerializer(many=True, read_only=True)

    class Meta:
        model = FollowMe
        fields = '__all__'
        read_only_fields = ['follow_me_uuid', 'insert_date', 'insert_user', 'update_date', 'update_user']
