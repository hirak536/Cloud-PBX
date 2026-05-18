from rest_framework import serializers
from .models import IvrMenu, IvrMenuOption


class IvrMenuOptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = IvrMenuOption
        fields = '__all__'
        read_only_fields = ['ivr_menu_option_uuid', 'ivr_menu', 'domain', 'tenant', 'insert_date', 'insert_user']


class IvrMenuSerializer(serializers.ModelSerializer):
    options = IvrMenuOptionSerializer(many=True, required=False)

    class Meta:
        model = IvrMenu
        fields = '__all__'
        read_only_fields = ['ivr_menu_uuid', 'domain', 'tenant', 'insert_date', 'insert_user', 'update_date', 'update_user']

    def _save_options(self, instance, options_data):
        instance.options.all().delete()
        for opt in options_data:
            opt.pop('ivr_menu_option_uuid', None)
            opt.pop('ivr_menu', None)
            opt.pop('insert_date', None)
            opt.pop('insert_user', None)
            IvrMenuOption.objects.create(
                ivr_menu=instance,
                tenant=instance.tenant,
                domain=instance.domain,
                **opt,
            )

    def validate(self, data):
        from apps.common.extension_conflict import check_extension_conflict
        from .models import IvrMenu
        tenant = (data.get('tenant')
                  or getattr(self.instance, 'tenant', None)
                  or self.context.get('tenant'))
        ext = data.get('ivr_menu_extension', getattr(self.instance, 'ivr_menu_extension', None))
        if ext and tenant:
            conflicts = check_extension_conflict(ext, tenant, exclude_model=IvrMenu)
            if conflicts:
                raise serializers.ValidationError({'ivr_menu_extension': conflicts[0]})
        return data

    def create(self, validated_data):
        options_data = validated_data.pop('options', [])
        instance = super().create(validated_data)
        self._save_options(instance, options_data)
        return instance

    def update(self, instance, validated_data):
        options_data = validated_data.pop('options', None)
        instance = super().update(instance, validated_data)
        if options_data is not None:
            self._save_options(instance, options_data)
        return instance


class IvrMenuListSerializer(serializers.ModelSerializer):
    class Meta:
        model = IvrMenu
        fields = ['ivr_menu_uuid', 'ivr_menu_name', 'ivr_menu_extension', 'ivr_menu_enabled']
