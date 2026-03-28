import random

# Create your views here.
from django.contrib.auth.models import User

from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .models import OTPSessions
from .serializers import OTPSerializer, UserSerializer


@api_view(["POST"])
def generate_otp(request):
    serializer = UserSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    email = serializer.validated_data["email"]
    if not User.objects.filter(email=email).exists():
        user = User.objects.create_user(username=email.split("@")[0], email=email)
        user.set_unusable_password()
        user.save()
    otp = str(random.randint(100000, 999999))  # noqa: S311
    otp_session = OTPSessions.objects.create(email=email, otp=otp)
    return Response("OTP generated successfully", status=status.HTTP_200_OK)


@api_view(["POST"])
def verify_otp(request):
    serializer = OTPSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    otp = serializer.validated_data["otp"]
    email = serializer.validated_data["email"]
    try:
        otp_session = OTPSessions.objects.get(email=email, otp=otp, verified=False)
    except OTPSessions.DoesNotExist:
        return Response("Invalid OTP", status=status.HTTP_400_BAD_REQUEST)
    otp_session.verified = True
    otp_session.save()
    return Response("OTP verified successfully", status=status.HTTP_200_OK)
