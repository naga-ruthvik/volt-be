from django.urls import path

from .views import (
    ActivitiesListView,
    GenerateRequestView,
    MetricsRetrieveView,
    PlatformListCreateView,
    PlatformUpdateDestroyView,
    RetrieveHackerRankStatsView,
    UserPlatformMetadataListView,
)

urlpatterns = [
    path(
        "platforms/",
        PlatformListCreateView.as_view(),
        name="platform-list-create",
    ),
    path(
        "platforms/<str:platform>/",
        PlatformUpdateDestroyView.as_view(),
        name="platform-update-destroy",
    ),
    path("generate/", GenerateRequestView.as_view(), name="generate-request"),
    path(
        "activities/",
        ActivitiesListView.as_view(),
        name="activities-list",
    ),
    path("metrics/", MetricsRetrieveView.as_view(), name="metrics-view"),
    path(
        "platforms-metadata/",
        UserPlatformMetadataListView.as_view(),
        name="platform-metadata-view",
    ),
]
