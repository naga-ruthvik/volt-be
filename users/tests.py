import email

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from rest_framework.test import APIClient

from .models import OTPSessions


class OTPTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.valid_email = "test@mail.co"
        self.invalid_email = "invalid_email"
        self.password = "password1234PASS"  # noqa: S105

    def test_otp_generation_success(self):
        url = reverse("generate_otp")
        response = self.client.post(
            path=url, data={"email": self.valid_email}, format="json"
        )
        self.assertEqual(response.status_code, 200)
        self.assertGreaterEqual(
            OTPSessions.objects.filter(email=self.valid_email).count(), 1
        )
        self.assertEqual(User.objects.filter(email=self.valid_email).count(), 1)

    def test_otp_generation_fail(self):
        url = reverse("generate_otp")
        response = self.client.post(
            path=url, data={"email": self.invalid_email}, format="json"
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(OTPSessions.objects.all().count(), 0)
        self.assertEqual(User.objects.all().count(), 0)

    def test_otp_verify_success(self):
        url_generate_otp = reverse("generate_otp")
        self.client.post(
            path=url_generate_otp, data={"email": self.valid_email}, format="json"
        )
        # Fetch the session from the database AFTER it's been created
        otp_session = OTPSessions.objects.get(email=self.valid_email, verified=False)
        generated_otp = otp_session.otp
        data = {"otp": generated_otp, "email": self.valid_email}
        url_verify_otp = reverse("verify_otp")
        response = self.client.post(path=url_verify_otp, data=data, format="json")

        # Refresh from DB since verify_otp modified it
        otp_session.refresh_from_db()

        self.assertEqual(response.status_code, 200)
        self.assertTrue(otp_session.verified)
        self.assertEqual(response.data, "OTP verified successfully")
        self.assertEqual(User.objects.filter(email=self.valid_email).count(), 1)
        self.assertEqual(
            OTPSessions.objects.filter(email=self.valid_email, verified=True).count(), 1
        )
        self.assertEqual(
            OTPSessions.objects.get(email=self.valid_email, verified=True).otp,
            generated_otp,
        )

    def test_otp_verify_invalid_otp(self):
        url_generate_otp = reverse("generate_otp")
        self.client.post(
            path=url_generate_otp, data={"email": self.valid_email}, format="json"
        )
        data = {"otp": "000000", "email": self.valid_email}
        url_verify_otp = reverse("verify_otp")
        response = self.client.post(path=url_verify_otp, data=data, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data, "Invalid OTP")

    def test_otp_verify_already_verified(self):
        url_generate_otp = reverse("generate_otp")
        self.client.post(
            path=url_generate_otp, data={"email": self.valid_email}, format="json"
        )
        otp_session = OTPSessions.objects.get(email=self.valid_email, verified=False)
        generated_otp = otp_session.otp
        data = {"otp": generated_otp, "email": self.valid_email}
        url_verify_otp = reverse("verify_otp")

        # Verify first time
        self.client.post(path=url_verify_otp, data=data, format="json")

        # Verify second time
        response = self.client.post(path=url_verify_otp, data=data, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data, "Invalid OTP")

    def test_otp_reuse_for_different_email(self):
        # Generate OTP for email 1
        self.client.post(
            path=reverse("generate_otp"), data={"email": "user1@mail.co"}, format="json"
        )
        otp_session = OTPSessions.objects.get(email="user1@mail.co")
        otp = otp_session.otp

        # Try to verify for email 2
        data = {"otp": otp, "email": "user2@mail.co"}
        response = self.client.post(
            path=reverse("verify_otp"), data=data, format="json"
        )
        self.assertEqual(response.status_code, 400)
