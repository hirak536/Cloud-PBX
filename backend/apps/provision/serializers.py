from rest_framework import serializers

from .models import ProvisionTemplate


class ProvisionTemplateListSerializer(serializers.ModelSerializer):
    """Compact serializer used for list endpoints (omits template_content)."""

    class Meta:
        model = ProvisionTemplate
        fields = [
            'template_uuid',
            'vendor',
            'model',
            'firmware_version',
            'template_name',
            'content_type',
            'is_active',
            'insert_date',
            'update_date',
        ]
        read_only_fields = ['template_uuid', 'insert_date', 'update_date']


class ProvisionTemplateSerializer(serializers.ModelSerializer):
    """Full serializer for create/retrieve/update operations."""

    class Meta:
        model = ProvisionTemplate
        fields = [
            'template_uuid',
            'vendor',
            'model',
            'firmware_version',
            'template_name',
            'template_content',
            'content_type',
            'is_active',
            'insert_date',
            'update_date',
        ]
        read_only_fields = ['template_uuid', 'insert_date', 'update_date']

    def validate_template_content(self, value):
        """Validate that the template compiles without syntax errors."""
        from django.template import Template, TemplateSyntaxError
        try:
            Template(value)
        except TemplateSyntaxError as exc:
            raise serializers.ValidationError(
                f'Invalid Django template syntax: {exc}'
            )
        return value

    def validate(self, attrs):
        """Enforce unique_together constraint on update."""
        vendor = attrs.get('vendor', getattr(self.instance, 'vendor', None))
        model = attrs.get('model', getattr(self.instance, 'model', ''))
        firmware_version = attrs.get(
            'firmware_version', getattr(self.instance, 'firmware_version', '')
        )
        template_name = attrs.get('template_name', getattr(self.instance, 'template_name', None))

        if vendor and template_name:
            qs = ProvisionTemplate.objects.filter(
                vendor=vendor,
                model=model,
                firmware_version=firmware_version,
                template_name=template_name,
            )
            if self.instance:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError(
                    'A template with this vendor/model/firmware_version/template_name already exists.'
                )
        return attrs
