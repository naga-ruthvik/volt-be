from datetime import date

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from .models import (
    Activity,
    GenerationRequest,
    Platform,
    PlatformAccount,
    UserMetrics,
)
from .services.metrics_service import MetricsService

User = get_user_model()


class PlatformAccountTest(TestCase):
    def setUp(self):
        self.email = "test@mail.com"
        self.user = self._create_user(username="testuser", email=self.email)
        token = RefreshToken.for_user(self.user)
        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token.access_token}')

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
        url = reverse("platform-list-create")
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
            url = reverse("platform-list-create")
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
        url = reverse("platform-list-create")
        response = self.client.get(path=url, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["platform"], platform_account.platform)
        self.assertEqual(response.data[0]["username"], platform_account.username)

    def test_duplicate_platform_not_allowed(self):
        self._create_platform_account()
        url = reverse("platform-list-create")
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
                "platform": platform_account.platform,
            },
        )
        new_username = "updated_username"
        response = self.client.patch(
            path=url, data={"username": new_username}, format="json"
        )
        platform_account.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(platform_account.username, new_username)
        self.assertEqual(response.data["username"], new_username)

    def test_delete_platform_account(self):
        platform_account = self._create_platform_account()
        url = reverse(
            "platform-update-destroy",
            kwargs={
                "platform": platform_account.platform,
            },
        )
        response = self.client.delete(path=url)
        self.assertEqual(response.status_code, 204)
        self.assertEqual(PlatformAccount.objects.count(), 0)

    def test_update_for_other_user_is_not_found(self):
        other_user = self._create_user(username="user3", email="user3@mail.com")
        PlatformAccount.objects.create(
            platform=Platform.CODECHEF,
            username="other_username",
            user=other_user,
        )
        url = reverse(
            "platform-update-destroy",
            kwargs={
                "platform": Platform.CODECHEF,
            },
        )
        response = self.client.get(path=url)
        self.assertEqual(response.status_code, 404)


class ActivitiesListViewTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="heatmap_user",
            email="heatmap@mail.com",
            password="password1234PASS",  # noqa: S106
        )
        token = RefreshToken.for_user(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token.access_token}")
        self.other_user = User.objects.create_user(
            username="other_user",
            email="other@mail.com",
            password="password1234PASS",  # noqa: S106
        )

    def _create_generation_request(self, user):
        return GenerationRequest.objects.create(user=user)

    def _create_activity(self, generation_request, platform, activity_date, count):
        return Activity.objects.create(
            user=generation_request.user,
            generation_request=generation_request,
            platform=platform,
            activity_date=activity_date,
            activity_count=count,
        )

    def test_list_activities_filters_by_username(self):
        user_request = self._create_generation_request(self.user)
        other_request = self._create_generation_request(self.other_user)

        self._create_activity(user_request, Platform.GITHUB, date(2026, 4, 1), 3)
        self._create_activity(other_request, Platform.GITHUB, date(2026, 4, 1), 7)

        url = reverse("activities-list")
        response = self.client.get(path=url, format="json")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["activity_count"], 3)

    def test_list_activities_filters_by_date_range(self):
        generation_request = self._create_generation_request(self.user)

        self._create_activity(generation_request, Platform.GITHUB, date(2026, 4, 1), 1)
        self._create_activity(generation_request, Platform.GITHUB, date(2026, 4, 2), 2)
        self._create_activity(generation_request, Platform.GITHUB, date(2026, 4, 3), 3)

        url = reverse("activities-list")
        response = self.client.get(
            path=url,
            data={"start_date": "2026-04-02", "end_date": "2026-04-03"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 2)
        self.assertEqual(response.data[0]["activity_date"], "2026-04-02")
        self.assertEqual(response.data[1]["activity_date"], "2026-04-03")

    def test_list_activities_rejects_invalid_dates(self):
        url = reverse("activities-list")
        response = self.client.get(path=url, data={"start_date": "2026-99-99"})

        self.assertEqual(response.status_code, 400)
        self.assertIn("start_date", response.data)

    def test_list_activities_rejects_reversed_date_range(self):
        url = reverse("activities-list")
        response = self.client.get(
            path=url,
            data={"start_date": "2026-04-10", "end_date": "2026-04-01"},
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("date_range", response.data)


class ActivityModelConstraintTest(TestCase):
    def test_activity_unique_together_is_scoped_per_user(self):
        user = User.objects.create_user(
            username="constraint_user",
            email="constraint@mail.com",
            password="password1234PASS",  # noqa: S106
        )
        generation_request_1 = GenerationRequest.objects.create(user=user)
        generation_request_2 = GenerationRequest.objects.create(user=user)

        Activity.objects.create(
            user=user,
            generation_request=generation_request_1,
            platform=Platform.GITHUB,
            activity_date=date(2026, 4, 1),
            activity_count=5,
        )

        with transaction.atomic():
            with self.assertRaises(IntegrityError):
                Activity.objects.create(
                    user=user,
                    generation_request=generation_request_1,
                    platform=Platform.GITHUB,
                    activity_date=date(2026, 4, 1),
                    activity_count=10,
                )

        with transaction.atomic():
            with self.assertRaises(IntegrityError):
                Activity.objects.create(
                    user=user,
                    generation_request=generation_request_2,
                    platform=Platform.GITHUB,
                    activity_date=date(2026, 4, 1),
                    activity_count=8,
                )


class MetricsServiceTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="metrics_user",
            email="metrics@mail.com",
            password="password1234PASS",  # noqa: S106
        )

    def _create_generation_request(self):
        return GenerationRequest.objects.create(user=self.user, status="completed")

    def _add_activity(self, generation_request, platform, year, month, day, count):
        return Activity.objects.update_or_create(
            user=generation_request.user,
            platform=platform,
            activity_date=date(year, month, day),
            defaults={
                "generation_request": generation_request,
                "activity_count": count,
            },
        )

    def test_generation_metrics_use_distinct_active_days(self):
        generation_request = self._create_generation_request()
        self._add_activity(generation_request, Platform.GITHUB, 2026, 4, 20, 1)
        self._add_activity(generation_request, Platform.CODEFORCES, 2026, 4, 20, 3)
        self._add_activity(generation_request, Platform.GITHUB, 2026, 4, 21, 2)

        metrics = MetricsService.calculate_metrics(generation_request)
        generation_metrics = metrics["generation_metrics"]

        self.assertEqual(generation_metrics["gen_active_days"], 2)
        self.assertEqual(generation_metrics["gen_total_activities"], 6)
        self.assertEqual(generation_metrics["gen_longest_streak"], 2)

    def test_user_metrics_accumulate_across_generations(self):
        generation_request_1 = self._create_generation_request()
        self._add_activity(generation_request_1, Platform.GITHUB, 2026, 4, 24, 1)
        self._add_activity(generation_request_1, Platform.GITHUB, 2026, 4, 25, 1)
        MetricsService.calculate_metrics(generation_request_1)

        generation_request_2 = self._create_generation_request()
        self._add_activity(generation_request_2, Platform.GITHUB, 2026, 4, 25, 1)
        self._add_activity(generation_request_2, Platform.GITHUB, 2026, 4, 26, 1)
        metrics = MetricsService.calculate_metrics(generation_request_2)
        user_metrics = metrics["user_metrics"]

        self.assertEqual(user_metrics["total_active_days"], 3)
        self.assertEqual(user_metrics["total_activities"], 3)
        self.assertEqual(user_metrics["current_streak"], 0)
        self.assertEqual(user_metrics["longest_streak"], 3)


class MetricsViewTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="metrics_view_user",
            email="metrics-view@mail.com",
            password="password1234PASS",  # noqa: S106
        )
        token = RefreshToken.for_user(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token.access_token}")

    def test_metrics_view_returns_user_and_generation_metrics(self):
        generation_request = GenerationRequest.objects.create(
            user=self.user, status="completed"
        )
        Activity.objects.create(
            user=self.user,
            generation_request=generation_request,
            platform=Platform.GITHUB,
            activity_date=date(2026, 4, 26),
            activity_count=2,
        )
        MetricsService.calculate_metrics(generation_request)

        url = reverse("metrics-view")
        response = self.client.get(
            path=url,
            data={"generation_request_id": str(generation_request.id)},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("user_metrics", response.data)
        self.assertIn("generation_metrics", response.data)
        self.assertEqual(
            response.data["generation_metrics"][0]["id"],
            generation_request.id,
        )
        self.assertEqual(UserMetrics.objects.filter(user=self.user).count(), 1)
