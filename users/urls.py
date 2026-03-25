from django.urls import path

from .views import generate_otp, verify_otp

urlpatterns = [
    path("otp/generate/", generate_otp, name="generate_otp"),
    path("otp/verify/", verify_otp, name="verify_otp"),
]
