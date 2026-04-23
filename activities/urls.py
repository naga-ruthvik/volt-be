from django.urls import path

from .views import (
    GenerateRequestView,
    PlatformListCreateView,
    PlatformUpdateDestroyView,
    ActivitiesListView,
)


urlpatterns = [
    path(
        "<str:username>/platforms/",
        PlatformListCreateView.as_view(),
        name="platform-list-create",
    ),
    path(
        "<str:username>/<str:platform_username>/<str:platform>/",
        PlatformUpdateDestroyView.as_view(),
        name="platform-update-destroy",
    ),
    path("generate/", GenerateRequestView.as_view(), name="generate-request"),
    path(
        "activities/<str:username>/",
        ActivitiesListView.as_view(),
        name="activities-list",
    ),
]
