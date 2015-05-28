from rest_framework import serializers
from cyder.base.log_serializer import BaseLogSerializer
from cyder.models import AddressRecord


class AddressRecordLogSerializer(BaseLogSerializer):
    domain = serializers.SlugRelatedField(slug_field="name")
    ip_address = serializers.CharField(source="ip_str")
    time_to_live = serializers.IntegerField(source="ttl")

    class Meta:
        model = AddressRecord
        fields = ("label", "domain", "ip_address", "last_save_user",
                  "time_to_live", "description")