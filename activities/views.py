from importlib.metadata import metadata

from django.shortcuts import get_object_or_404
from django.utils.dateparse import parse_date

from rest_framework import generics, status
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Activity, GenerationRequest, Platform, PlatformAccount, UserMetrics
from .serializers import (
    ActivityListSerializer,
    GenerationMetricsSerializer,
    HackerRankStatsSerializer,
    PlatformCreateSerializer,
    PlatformListSerializer,
    PlatformUpdateSerializer,
    UserMetricsSerializer,
    UserPlatformMetadataSerializer,
)
from .services.metrics_service import MetricsService
from .services.sync_service import SyncService


# platform views
class PlatformListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return PlatformAccount.objects.filter(user=self.request.user)

    def get_serializer_class(self):
        if self.request.method == "POST":
            return PlatformCreateSerializer
        return PlatformListSerializer

    def perform_create(self, serializer):
        return serializer.save(user=self.request.user)


class PlatformUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    queryset = PlatformAccount.objects.all()
    permission_classes = [IsAuthenticated]

    def get_object(self):
        platform = self.kwargs.get("platform")
        return get_object_or_404(
            PlatformAccount,
            user=self.request.user,
            platform=platform,
        )

    def get_serializer_class(self):
        if self.request.method in ["PUT", "PATCH"]:
            return PlatformUpdateSerializer
        return PlatformListSerializer


# activity views
class GenerateRequestView(generics.CreateAPIView):
    permission_classes = [IsAuthenticated]

    def create(self, request, *args, **kwargs):
        generation_request = GenerationRequest.objects.create(user=request.user)
        # TODO: move this to async (Celery)
        SyncService.sync_all_platforms(generation_request)
        return Response(
            {"message": "Generation request created and data synced successfully"},
            status=status.HTTP_200_OK,
        )


class ActivitiesListView(generics.ListCreateAPIView):
    queryset = Activity.objects.all()
    serializer_class = ActivityListSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = Activity.objects.filter(user=self.request.user)
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


class MetricsRetrieveView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        try:
            user_metrics = UserMetrics.objects.get(user=self.request.user)
            generation_metrics = (
                GenerationRequest.objects.filter(user=self.request.user)
                .order_by("-created_at")
                .all()
            )
        except UserMetrics.DoesNotExist:
            return Response(
                {"error": "User metrics not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        payload = {
            "user_metrics": UserMetricsSerializer(user_metrics).data,
            "generation_metrics": GenerationMetricsSerializer(
                generation_metrics, many=True
            ).data,
        }
        return Response(payload, status=status.HTTP_200_OK)


class RetrieveHackerRankStatsView(generics.RetrieveAPIView):
    serializer_class = HackerRankStatsSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return PlatformAccount.objects.get(
            user=self.request.user,
            platform=Platform.HACKERRANK,
        )


class UserPlatformMetadataListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        platform_metadata = MetricsService.get_platform_metadata(self.request.user)
        wrapped_payload = {"platforms": platform_metadata}
        serializer = UserPlatformMetadataSerializer(instance=wrapped_payload)
        return Response(serializer.data, status=status.HTTP_200_OK)
