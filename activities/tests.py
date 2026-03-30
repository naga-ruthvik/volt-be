from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from rest_framework.test import APIClient

from .models import Platform, PlatformAccount


class PlatformAccountTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.email = "test@mail.com"
        self.user = self._create_user(username="testuser", email=self.email)

    def _create_user(self, username, email):
        return User.objects.create_user(
            username=username,
            email=email,
            password="password1234PASS",  # noqa: S106
        )

    def _create_platform_account(self, **kwargs):
        defaults = {
            "platform": Platform.CODECHEF,
            "username": "test_codechef",
            "user": self.user,
        }
        defaults.update(kwargs)
        return PlatformAccount.objects.create(**defaults)

    def test_create_platform_account(self):
        url = reverse("platform-list-create", kwargs={"username": self.user.username})
        data = {
            "user": self.user.id,
            "platform": Platform.CODECHEF,
            "username": "test_codechef",
        }
        response = self.client.post(path=url, data=data, format="json")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(PlatformAccount.objects.count(), 1)
        platform_account = PlatformAccount.objects.first()
        self.assertEqual(platform_account.platform, "codechef")
        self.assertEqual(platform_account.username, "test_codechef")

    def test_create_all_platform_accounts(self):
        platforms = [
            Platform.CODECHEF,
            Platform.CODEFORCES,
            Platform.HACKERRANK,
            Platform.GITHUB,
            Platform.LEETCODE,
        ]
        for platform in platforms:
            url = reverse(
                "platform-list-create", kwargs={"username": self.user.username}
            )
            data = {
                "user": self.user.id,
                "platform": platform,
                "username": f"test_{platform}",
            }
            response = self.client.post(path=url, data=data, format="json")
            self.assertEqual(response.status_code, 201)

        self.assertEqual(PlatformAccount.objects.count(), 5)

    def test_list_platform_accounts(self):
        platform_account = self._create_platform_account()
        other_user = self._create_user(username="user2", email="user2@mail.com")
        PlatformAccount.objects.create(
            platform=Platform.GITHUB, username="other", user=other_user
        )
        url = reverse("platform-list-create", kwargs={"username": self.user.username})
        response = self.client.get(path=url, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["platform"], platform_account.platform)
        self.assertEqual(response.data[0]["username"], platform_account.username)

    def test_duplicate_platform_not_allowed(self):
        self._create_platform_account()
        url = reverse("platform-list-create", kwargs={"username": self.user.username})
        data = {
            "user": self.user.id,
            "platform": Platform.CODECHEF,
            "username": "another_username",
        }
        response = self.client.post(path=url, data=data, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("non_field_errors", response.data)

    def test_retrieve_platform_account(self):
        platform_account = self._create_platform_account()
        url = reverse(
            "platform-update-destroy",
            kwargs={
                "username": self.user.username,
                "platform_username": platform_account.username,
                "platform": platform_account.platform,
            },
        )
        response = self.client.get(path=url, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["platform"], platform_account.platform)
        self.assertEqual(response.data["username"], platform_account.username)

    def test_update_platform_username(self):
        platform_account = self._create_platform_account()
        url = reverse(
            "platform-update-destroy",
            kwargs={
                "username": self.user.username,
                "platform_username": platform_account.username,
                "platform": platform_account.platform,
            },
        )
        new_username = "updated_username"
        response = self.client.patch(path=url, data={"username": new_username}, format="json")
        platform_account.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(platform_account.username, new_username)
        self.assertEqual(response.data["username"], new_username)

    def test_delete_platform_account(self):
        platform_account = self._create_platform_account()
        url = reverse(
            "platform-update-destroy",
            kwargs={
                "username": self.user.username,
                "platform_username": platform_account.username,
                "platform": platform_account.platform,
            },
        )
        response = self.client.delete(path=url)
        self.assertEqual(response.status_code, 204)
        self.assertEqual(PlatformAccount.objects.count(), 0)

    def test_update_for_other_user_is_not_found(self):
        platform_account = self._create_platform_account()
        other_user = self._create_user(username="user3", email="user3@mail.com")
        url = reverse(
            "platform-update-destroy",
            kwargs={
                "username": other_user.username,
                "platform_username": platform_account.username,
                "platform": platform_account.platform,
            },
        )
        response = self.client.get(path=url)
        self.assertEqual(response.status_code, 404)

