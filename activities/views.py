from django.contrib.auth.models import User
from django.shortcuts import get_object_or_404

from rest_framework import generics, status
from rest_framework.response import Response

from .models import PlatformAccount
from .serializers import (
    GenerateRequestsCreateSerializer,
    PlatformCreateSerializer,
    PlatformListSerializer,
    PlatformUpdateSerializer,
)
from .services.sync_service import SyncService


class PlatformListCreateView(generics.ListCreateAPIView):
    queryset = PlatformAccount.objects.all()

    def get_queryset(self):
        username = self.kwargs.get("username")
        return PlatformAccount.objects.filter(user__username=username)

    def get_serializer_class(self):
        if self.request.method == "POST":
            return PlatformCreateSerializer
        return PlatformListSerializer


class PlatformUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    queryset = PlatformAccount.objects.all()

    def get_object(self):
        username = self.kwargs.get("username")
        platform_username = self.kwargs.get("platform_username")
        platform = self.kwargs.get("platform")
        return get_object_or_404(
            PlatformAccount,
            user__username=username,
            username=platform_username,
            platform=platform,
        )

    def get_serializer_class(self):
        if self.request.method in ["PUT", "PATCH"]:
            return PlatformUpdateSerializer
        return PlatformListSerializer


class GenerateRequestView(generics.CreateAPIView):
    serializer_class = GenerateRequestsCreateSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        print(serializer.validated_data)
        # TODO: RELACE BY ADDING AUTHENTICATION
        user = User.objects.get(username=serializer.validated_data["user"]["username"])
        generation_request = serializer.save(user=user)
        # TODO: move this to async (Celery)
        SyncService.sync_all_platforms(generation_request)
        return Response(
            {"message": "Generation request created and data synced successfully"},
            status=status.HTTP_200_OK,
        )
