from rest_framework import serializers
from .models import Asset, SystemMessage


class AssetSerializer(serializers.ModelSerializer):
    class Meta:
        model = Asset
        fields = '__all__'


class SystemMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = SystemMessage
        fields = ['id', 'timestamp', 'level', 'component', 'message']