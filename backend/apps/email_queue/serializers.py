from rest_framework import serializers
from .models import EmailQueue

class EmailQueueSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmailQueue
        fields = '__all__'
        read_only_fields = ['email_queue_uuid', 'insert_date', 'insert_user']
