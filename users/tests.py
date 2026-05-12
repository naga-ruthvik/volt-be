import random
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import check_password
from django.test import TestCase
from django.urls import reverse

from rest_framework.test import APIClient

from .models import OTPSessions

User = get_user_model()


class OTPTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.valid_email = "test@mail.co"
        self.invalid_email = "invalid_email"
        self.valid_username = "testuser"

    # generation tests
    @patch("users.views.random.randint")
    def test_otp_generation_success(self, mock_randint):
        mock_randint.return_value = 123456
        url = reverse("generate_otp")
        response = self.client.post(
            path=url,
            data={"email": self.valid_email},
            format="json",
        )
        otp_session = OTPSessions.objects.filter(
            email=self.valid_email, verified=False
        ).latest("created_at")
        hashed_otp = otp_session.otp
        self.assertEqual(response.status_code, 200)
        self.assertGreaterEqual(
            OTPSessions.objects.filter(email=self.valid_email).count(), 1
        )
        self.assertTrue(otp_session.is_valid)
        self.assertFalse(otp_session.verified)
        self.assertEqual(User.objects.filter(email=self.valid_email).count(), 0) # User should not be created here anymore
        self.assertNotEqual(hashed_otp, "123456")
        self.assertEqual(check_password("123456", hashed_otp), True)
        self.assertIn("message", response.data)
        self.assertEqual(response.data["message"], "OTP generated successfully")
        self.assertTrue(response.data["is_new_user"])

    def test_otp_generation_fail(self):
        url = reverse("generate_otp")
        response = self.client.post(
            path=url,
            data={"email": self.invalid_email},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("error", response.data)
        self.assertEqual(response.data["error"], "Validation failed")
        self.assertEqual(OTPSessions.objects.all().count(), 0)
        self.assertEqual(User.objects.all().count(), 0)

    # verification tests
    @patch("users.views.random.randint")
    def test_otp_verify_success(self, mock_randint):
        url_generate_otp = reverse("generate_otp")
        mock_randint.return_value = 123456
        self.client.post(
            path=url_generate_otp,
            data={"email": self.valid_email},
            format="json",
        )
        # Fetch the session from the database AFTER it's been created
        otp_session = OTPSessions.objects.get(email=self.valid_email, verified=False)
        data = {"otp": "123456", "email": self.valid_email}
        url_verify_otp = reverse("verify_otp")
        response = self.client.post(path=url_verify_otp, data=data, format="json")

        # Refresh from DB since verify_otp modified it
        otp_session.refresh_from_db()

        self.assertEqual(response.status_code, 200)
        self.assertTrue(otp_session.verified)
        self.assertFalse(otp_session.is_valid)
        self.assertEqual(response.data["message"], "OTP verified successfully")
        self.assertTrue(response.data["registration_incomplete"])
        self.assertIsNone(response.data["user"]["username"])
        self.assertIn("access_token", response.data)
        self.assertIn("refresh_token", response.cookies)
        self.assertEqual(User.objects.filter(email=self.valid_email).count(), 1)
        self.assertEqual(User.objects.get(email=self.valid_email).token_version, 1)

    def test_otp_verify_invalid_otp(self):
        url_generate_otp = reverse("generate_otp")
        otp = str(random.randint(100000, 999999))  # noqa: S311
        self.client.post(
            path=url_generate_otp,
            data={"email": self.valid_email},
            format="json",
        )
        data = {"otp": otp, "email": self.valid_email}
        url_verify_otp = reverse("verify_otp")
        response = self.client.post(path=url_verify_otp, data=data, format="json")
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.data.get("error"), "Invalid OTP")

    def test_otp_verify_already_verified(self):
        url_generate_otp = reverse("generate_otp")
        self.client.post(
            path=url_generate_otp,
            data={"email": self.valid_email},
            format="json",
        )

        # Mocking check_password because we don't know the exact random otp here. Ohrs wait:
        # We need to fetch the session password to check
        otp_session = OTPSessions.objects.filter(
            email=self.valid_email, verified=False
        ).latest("created_at")
        # We bypass verify API to just mark it verified manually to simulate "already verified"
        otp_session.verified = True
        otp_session.is_valid = False
        otp_session.save()

        data = {"otp": "123456", "email": self.valid_email}
        url_verify_otp = reverse("verify_otp")
        response = self.client.post(
            path=url_verify_otp,
            data=data,
            format="json",
        )
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.data.get("error"), "Invalid or expired OTP")

    def test_otp_reuse_for_different_email(self):
        # Generate OTP for email 1
        self.client.post(
            path=reverse("generate_otp"),
            data={"email": "user1@mail.co"},
            format="json",
        )
        # Try to verify for email 2
        data = {"otp": "123456", "email": "user2@mail.co"}
        response = self.client.post(
            path=reverse("verify_otp"), data=data, format="json"
        )
        # Should end up as 401 Invalid or expired because email 2 has no sessions
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.data.get("error"), "Invalid or expired OTP")

    def test_complete_profile_success(self):
        # Create a user with incomplete profile
        user = User.objects.create_user(username="user_temp123", email="newuser@example.com")
        self.client.force_authenticate(user=user)

        response = self.client.post(
            reverse("complete_profile"),
            data={"username": "supercoolname"},
            format="json"
        )

        self.assertEqual(response.status_code, 200)
        user.refresh_from_db()
        self.assertEqual(user.username, "supercoolname")
        self.assertEqual(response.data["user"]["username"], "supercoolname")

    def test_complete_profile_username_taken(self):
        # User 1 takes username
        User.objects.create_user(username="takenname", email="first@example.com")

        # User 2 tries to take it
        user = User.objects.create_user(username="user_temp123", email="newuser@example.com")
        self.client.force_authenticate(user=user)

        response = self.client.post(
            reverse("complete_profile"),
            data={"username": "takenname"},
            format="json"
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("username", response.data["details"])

    # TODO: Add rate limit tests for OTP generation and verification in the future


class TokenTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.email = "test@mail.co"
        self.username = "testuser"
        self.user = User.objects.create_user(username=self.username, email=self.email)

    def test_refresh_token_success(self):
        from users.views import get_tokens_for_user

        tokens = get_tokens_for_user(self.user)
        self.client.cookies["refresh_token"] = tokens["refresh"]

        response = self.client.post(reverse("refresh_token"))
        self.assertEqual(response.status_code, 200)
        self.assertIn("access_token", response.data)
        self.assertIn("refresh_token", response.cookies)
        self.assertNotEqual(tokens["refresh"], response.cookies["refresh_token"].value)

    def test_refresh_token_version_mismatch(self):
        from users.views import get_tokens_for_user

        tokens = get_tokens_for_user(self.user)
        self.client.cookies["refresh_token"] = tokens["refresh"]

        # Invalidate tokens
        self.user.invalidate_all_tokens()

        response = self.client.post(reverse("refresh_token"))
        self.assertEqual(response.status_code, 401)
        self.assertIn(
            "Session expired (token version mismatch)", response.data.get("error", "")
        )

    def test_logout_success(self):
        from users.views import get_tokens_for_user

        tokens = get_tokens_for_user(self.user)
        self.client.cookies["refresh_token"] = tokens["refresh"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")

        baseline_version = self.user.token_version
        response = self.client.post(reverse("logout"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["message"], "Successfully logged out.")
        self.assertEqual(response.cookies["refresh_token"].value, "")  # cookie deleted

        self.user.refresh_from_db()
        self.assertEqual(self.user.token_version, baseline_version + 1)
