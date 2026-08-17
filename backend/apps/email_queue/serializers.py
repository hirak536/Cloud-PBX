from rest_framework import serializers
from .models import EmailQueue, EmailDelivery

class EmailQueueSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmailQueue
        fields = '__all__'
        read_only_fields = ['email_queue_uuid', 'insert_date', 'insert_user']


class EmailDeliverySerializer(serializers.ModelSerializer):
    class Meta:
        model = EmailDelivery
        fields = '__all__'
        read_only_fields = fields
