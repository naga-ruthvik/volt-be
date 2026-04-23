from django.contrib.auth.models import User
from django.shortcuts import get_object_or_404
from django.utils.dateparse import parse_date

from rest_framework import generics, status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from .models import Activity, PlatformAccount
from .serializers import (
    ActivityListSerializer,
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
        # TODO: RELACE BY ADDING AUTHENTICATION
        user = User.objects.get(username=serializer.validated_data["user"]["username"])
        generation_request = serializer.save(user=user)
        # TODO: move this to async (Celery)
        SyncService.sync_all_platforms(generation_request)
        return Response(
            {"message": "Generation request created and data synced successfully"},
            status=status.HTTP_200_OK,
        )


class ActivitiesListView(generics.ListCreateAPIView):
    queryset = Activity.objects.all()
    serializer_class = ActivityListSerializer

    def get_queryset(self):
        username = self.kwargs.get("username")
        queryset = Activity.objects.filter(generation_request__user__username=username)

        platform = self.request.query_params.get("platform")
        if platform:
            queryset = queryset.filter(platform=platform)

        start_date_param = self.request.query_params.get("start_date")
        end_date_param = self.request.query_params.get("end_date")

        start_date = None
        end_date = None

        if start_date_param:
            try:
                start_date = parse_date(start_date_param)
            except ValueError:
                start_date = None
            if start_date is None:
                raise ValidationError(
                    {"start_date": "Invalid date format. Use YYYY-MM-DD."}
                )

        if end_date_param:
            try:
                end_date = parse_date(end_date_param)
            except ValueError:
                end_date = None
            if end_date is None:
                raise ValidationError(
                    {"end_date": "Invalid date format. Use YYYY-MM-DD."}
                )

        if start_date and end_date and start_date > end_date:
            raise ValidationError(
                {"date_range": "start_date must be less than or equal to end_date."}
            )

        if start_date:
            queryset = queryset.filter(activity_date__gte=start_date)
        if end_date:
            queryset = queryset.filter(activity_date__lte=end_date)

        return queryset.order_by("activity_date", "platform", "id")
