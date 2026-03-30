from django.shortcuts import get_object_or_404

from rest_framework import generics

from .models import PlatformAccount
from .serializers import (
    PlatformCreateSerializer,
    PlatformListSerializer,
    PlatformUpdateSerializer,
)


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
