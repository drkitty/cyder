from rest_framework import serializers
from cyder.base.log_serializer import BaseLogSerializer
from cyder.models import StaticInterface


class StaticInterfaceLogSerializer(BaseLogSerializer):
    container = serializers.SlugRelatedField(slug_field='name', source='ctnr')
    reverse_domain = serializers.SlugRelatedField(slug_field='name')
    system = serializers.SlugRelatedField(slug_field='name')
    workgroup = serializers.SlugRelatedField(slug_field='name')
    expire = serializers.DateTimeField(format="%m/%d/%Y")
    ip = serializers.CharField(source="ip_str")

    class Meta:
        model = StaticInterface
        fields = ('container', 'mac', 'reverse_domain', 'system', 'workgroup',
                  'dhcp_enabled', 'dns_enabled', 'ip', 'last_save_user',
                  'description', 'expire')