from rest_framework import serializers
from kismet.models import Asset

class AssetMgrSerializer(serializers.ModelSerializer):
    class Meta:
        model = Asset
        fields = [
            'id', 'mac_address', 'vendor_oui', 'asset_type', 'ssid_alias',
            'is_whitelisted', 'smoothed_rssi', 'estimated_radius_meters',
            'operating_channel', 'first_seen', 'last_seen'
        ]
        read_only_fields = ['id', 'smoothed_rssi', 'estimated_radius_meters', 'first_seen', 'last_seen']
