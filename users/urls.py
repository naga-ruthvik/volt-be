from django.urls import path

from .views import (
    complete_profile,
    generate_otp,
    logout_view,
    refresh_token_view,
    verify_otp,
)

urlpatterns = [
    path("otp/generate/", generate_otp, name="generate_otp"),
    path("otp/verify/", verify_otp, name="verify_otp"),
    path("refresh/", refresh_token_view, name="refresh_token"),
    path("logout/", logout_view, name="logout"),
    path("profile/complete/", complete_profile, name="complete_profile"),
]
