from rest_framework import serializers
from .models import NumberTranslation, NumberTranslationDetail

class NumberTranslationDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = NumberTranslationDetail
        fields = '__all__'
        read_only_fields = ['number_translation_detail_uuid', 'insert_date']

class NumberTranslationSerializer(serializers.ModelSerializer):
    details = NumberTranslationDetailSerializer(many=True, read_only=True)

    class Meta:
        model = NumberTranslation
        fields = '__all__'
        read_only_fields = ['number_translation_uuid', 'insert_date', 'insert_user', 'update_date', 'update_user']
