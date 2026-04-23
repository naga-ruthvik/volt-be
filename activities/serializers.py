from rest_framework import serializers

from .models import Activity, GenerationRequest, PlatformAccount


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


class GenerateRequestsCreateSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username")

    class Meta:
        model = GenerationRequest
        fields = ["username"]


class ActivityListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Activity
        fields = ["id", "platform", "activity_date", "activity_count", "metadata"]
