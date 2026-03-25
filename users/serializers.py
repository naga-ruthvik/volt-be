from django.contrib.auth.models import User

from rest_framework import serializers


class UserSerializer(serializers.ModelSerializer):
    """
    Serializer to create and list users.
    Only email field is required for creation, and only email field is returned in the response.
    """

    class Meta:
        model = User
        fields = ["email"]


class OTPSerializer(serializers.Serializer):
    otp = serializers.CharField(max_length=6, min_length=6)
    email = serializers.EmailField()
