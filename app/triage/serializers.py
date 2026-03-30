from rest_framework import serializers
from kismet.models import SecurityEvent, HunterDispatchLog


class SecurityEventSerializer(serializers.ModelSerializer):
    asset_mac        = serializers.CharField(source='asset.mac_address', read_only=True)
    asset_vendor     = serializers.CharField(source='asset.vendor_oui', read_only=True)
    asset_type       = serializers.CharField(source='asset.asset_type', read_only=True)
    asset_rssi       = serializers.IntegerField(source='asset.smoothed_rssi', read_only=True)
    asset_radius     = serializers.FloatField(source='asset.estimated_radius_meters', read_only=True)
    asset_channel    = serializers.IntegerField(source='asset.operating_channel', read_only=True)
    asset_first_seen = serializers.DateTimeField(source='asset.first_seen', read_only=True)

    class Meta:
        model = SecurityEvent
        fields = '__all__'


class HunterDispatchLogSerializer(serializers.ModelSerializer):
    target_mac = serializers.CharField(source='target_asset.mac_address', read_only=True)

    class Meta:
        model = HunterDispatchLog
        fields = '__all__'
