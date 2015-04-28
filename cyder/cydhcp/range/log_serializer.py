from rest_framework import serializers
from cyder.base.log_serializer import BaseLogSerializer
from cyder.cydhcp.range.models import Range


class RangeLogSerializer(BaseLogSerializer):
    network = serializers.SerializerMethodField('get_network_representation')
    domain = serializers.SlugRelatedField(slug_field='name')
    range_type = serializers.SerializerMethodField('repr_range_type')
    start_address = serializers.CharField(source="start_str")
    end_address = serializers.CharField(source="end_str")

    class Meta:
        model = Range
        fields = ('name', 'network', 'range_type', 'ip_type', 'start_address',
                  'end_address', 'domain', 'is_reserved', 'allow',
                  'dhcpd_raw_include', 'dhcp_enabled', 'description',
                  'last_save_user')

    def get_network_representation(self, obj):
        return str(obj.network)

    def repr_range_type(self, obj):
        return {'st': 'static', 'dy': 'dynamic'}.get(obj.range_type, "unknown")
