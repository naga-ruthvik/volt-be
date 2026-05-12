from django.contrib.auth import get_user_model

from rest_framework import serializers

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    """
    Serializer to list users.
    """
    class Meta:
        model = User
        fields = ["email", "username"]


class EmailOnlySerializer(serializers.Serializer):
    email = serializers.EmailField()


class ProfileUpdateSerializer(serializers.Serializer):
    username = serializers.CharField()


class OTPSerializer(serializers.Serializer):
    otp = serializers.CharField(max_length=6, min_length=6)
    email = serializers.EmailField()
