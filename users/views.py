import logging
import random
import uuid

from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import check_password, make_password
from django.utils import timezone

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken

from common.email.service import EmailService

from .models import OTPSessions
from .serializers import (
    EmailOnlySerializer,
    OTPSerializer,
    ProfileUpdateSerializer,
    UserSerializer,
)

logger = logging.getLogger(__name__)

User = get_user_model()


def get_tokens_for_user(user):
    refresh = RefreshToken.for_user(user)
    # Add custom claims if needed
    refresh["email"] = user.email
    refresh["token_version"] = user.token_version
    return {
        "refresh": str(refresh),
        "access": str(refresh.access_token),
    }


def mask_email(email):
    try:
        name, domain = email.split("@")
        masked_name = name[0] + "***" if len(name) > 1 else "***"
        return f"{masked_name}@{domain}"
    except ValueError:
        return email


@api_view(["POST"])
@permission_classes([AllowAny])
def generate_otp(request):
    logger.info("generate otp called")
    serializer = EmailOnlySerializer(data=request.data)
    if not serializer.is_valid():
        logger.warning("validation failed: %s", serializer.errors)
        return Response(
            {"error": "Validation failed", "details": serializer.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )
    email = serializer.validated_data["email"]

    is_new_user = not User.objects.filter(email=email).exists()

    logger.info("Generating OTP for %s", email)
    otp = str(random.randint(100000, 999999))  # noqa: S311
    hashed_otp = make_password(otp)

    # Invalidate older unpaid OTPs could be done here
    OTPSessions.objects.filter(email=email, verified=False).update(is_valid=False)

    otp_session = OTPSessions.objects.create(email=email, otp=hashed_otp, is_valid=True)

    # Normally we would send email here... print to console for dev
    # TODO: send otp in email
    EmailService.send_otp_email(email, otp)
    print(f"OTP for {email}: {otp}")

    return Response(
        {
            "message": "OTP generated successfully",
            "email": mask_email(email),
            "is_new_user": is_new_user,
        },
        status=status.HTTP_200_OK,
    )


@api_view(["POST"])
@permission_classes([AllowAny])
def verify_otp(request):
    logger.info("request to verify otp")
    serializer = OTPSerializer(data=request.data)
    if not serializer.is_valid():
        logger.warning("validation failed: %s", serializer.errors)
        return Response(
            {"error": "Validation failed", "details": serializer.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )
    otp = serializer.validated_data["otp"]
    email = serializer.validated_data["email"]

    try:
        logger.info("check if otp exists in table otp_sessions")
        otp_session = OTPSessions.objects.filter(
            email=email, verified=False, is_valid=True, expires_at__gt=timezone.now()
        ).latest("created_at")
    except OTPSessions.DoesNotExist:
        logger.error("No valid OTP session found for %s", email)
        return Response(
            {"error": "Invalid or expired OTP"}, status=status.HTTP_401_UNAUTHORIZED
        )

    if not check_password(otp, otp_session.otp):
        logger.warning("invalid otp provided for %s", email)
        return Response({"error": "Invalid OTP"}, status=status.HTTP_401_UNAUTHORIZED)

    otp_session.verified = True
    otp_session.is_valid = False
    otp_session.save()

    registration_incomplete = False
    try:
        user = User.objects.get(email=email)
    except User.DoesNotExist:
        # Create uninitialized account
        placeholder_username = f"user_{uuid.uuid4().hex[:10]}"
        user = User.objects.create_user(username=placeholder_username, email=email)
        registration_incomplete = True

    user.token_version += 1
    user.last_login = timezone.now()
    user.save(update_fields=["token_version", "last_login"])

    logger.info("get tokens for the user")
    tokens = get_tokens_for_user(user)

    response = Response(
        {
            "message": "OTP verified successfully",
            "access_token": tokens["access"],
            "user": {
                "email": user.email,
                "username": user.username if not registration_incomplete else None,
            },
            "registration_incomplete": registration_incomplete,
        },
        status=status.HTTP_200_OK,
    )
    logger.info("set refresh token cookie")
    response.set_cookie(
        key="refresh_token",
        value=tokens["refresh"],
        httponly=True,
        secure=True,
        samesite="None",
        max_age=7 * 24 * 60 * 60,  # 7 days
    )
    return response


@api_view(["POST"])
@permission_classes([AllowAny])
def refresh_token_view(request):
    logger.info("refresh token request received")
    logger.info("check if refresh token is present in cookies")
    refresh_token = request.COOKIES.get("refresh_token")
    if not refresh_token:
        logger.warning("refresh token not found in cookies")
        return Response(
            {"error": "Refresh token not found"}, status=status.HTTP_401_UNAUTHORIZED
        )

    try:
        logger.info("instantiate refresh token object")
        refresh = RefreshToken(refresh_token)

        # Verify token version if using custom claims
        logger.info(
            "check if the refresh token's version matches the user's token version"
        )
        user_id = refresh.payload.get("user_id")
        user = User.objects.get(id=user_id)
        if refresh.payload.get("token_version") != user.token_version:
            logger.warning("token version mismatch for user %s", user.email)
            return Response(
                {"error": "Session expired (token version mismatch)"},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        # Rotate
        logger.info("blacklist existing tokens")
        refresh.blacklist()
        logger.info("get tokens for the user")
        tokens = get_tokens_for_user(user)

        response = Response(
            {"access_token": tokens["access"]}, status=status.HTTP_200_OK
        )
        logger.info("set the new cookie with the new refresh token")
        response.set_cookie(
            key="refresh_token",
            value=tokens["refresh"],
            httponly=True,
            secure=True,
            samesite="None",
            max_age=7 * 24 * 60 * 60,
        )
        return response

    except Exception as e:
        logger.error("error during token refresh: %s", str(e))
        return Response({"error": str(e)}, status=status.HTTP_401_UNAUTHORIZED)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def logout_view(request):
    logger.info("logout request received")
    try:
        logger.info("check if refresh token is presented")
        refresh_token = request.COOKIES.get("refresh_token")
        if refresh_token:
            logger.info("refresh token is present and blacklist it")
            token = RefreshToken(refresh_token)
            token.blacklist()

        logger.info("invalidate all the tokens of the user")
        request.user.invalidate_all_tokens()

        response = Response(
            {"message": "Successfully logged out."}, status=status.HTTP_200_OK
        )
        logger.info("delete refresh token cookie")
        response.delete_cookie("refresh_token", samesite="None")
        return response
    except Exception as e:
        logger.error("error while logging out: %s", e)
        return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def complete_profile(request):
    logger.info("complete profile request received")
    serializer = ProfileUpdateSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(
            {"error": "Validation failed", "details": serializer.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )

    username = serializer.validated_data["username"]
    
    if User.objects.filter(username=username).exclude(id=request.user.id).exists():
        return Response(
            {
                "error": "Validation failed",
                "details": {"username": ["This username is already taken."]},
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    user = request.user
    user.username = username
    user.save(update_fields=["username"])

    return Response(
        {
            "message": "Profile updated successfully.",
            "user": {"email": user.email, "username": user.username},
        },
        status=status.HTTP_200_OK,
    )
