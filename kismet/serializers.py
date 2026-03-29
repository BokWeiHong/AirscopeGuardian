from rest_framework import serializers
from .models import Asset, SecurityEvent, HunterDispatchLog, SystemMessage


class AssetSerializer(serializers.ModelSerializer):
    class Meta:
        model = Asset
        fields = "__all__"


class SecurityEventSerializer(serializers.ModelSerializer):
    asset_mac = serializers.CharField(source='asset.mac_address', read_only=True)

    class Meta:
        model = SecurityEvent
        fields = "__all__"


class HunterDispatchLogSerializer(serializers.ModelSerializer):
    target_mac = serializers.CharField(source='target_asset.mac_address', read_only=True)

    class Meta:
        model = HunterDispatchLog
        fields = "__all__"


class SystemMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = SystemMessage
        fields = ['id', 'timestamp', 'level', 'component', 'message']