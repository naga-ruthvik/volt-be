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
