from rest_framework import serializers
from .models import PlatformAccount


class PlatformListSerializer(serializers.ModelSerializer):
    class Meta:
        model = PlatformAccount
        fields = ["id", "platform", "username"]


class PlatformCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = PlatformAccount
        fields = ["user", "platform", "username"]


class PlatformUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = PlatformAccount
        fields = ["username"]
