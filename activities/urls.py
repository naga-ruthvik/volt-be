from django.urls import path

from .views import PlatformListCreateView, PlatformUpdateDestroyView

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
]
