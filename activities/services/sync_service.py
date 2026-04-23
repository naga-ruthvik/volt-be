from datetime import datetime

from django.db import transaction
from django.utils import timezone

from activities.models import Activity, GenerationRequest, Platform, PlatformAccount
from activities.services.activity_service import ActivityService
from activities.services.metrics_service import MetricsService
from activities.services.normalization import ActivityNormalization
from activities.services.platforms.codeforces_service import CodeforcesService
from activities.services.platforms.github_service import GitHubService

from .activity_service import ActivityService
from .metrics_service import MetricsService
from .test.normalization_test import normalizer


class SyncService:
    @staticmethod
    def sync_github_data(username):
        github_service = GitHubService()
        normalizer = ActivityNormalization()
        events = github_service.fetch_events(username)
        return normalizer.github_activity_normalizer(events)

    @staticmethod
    def sync_codeforces_data(username):
        codeforces_service = CodeforcesService()
        events = codeforces_service.fetch_activities(username)
        normalizer = ActivityNormalization()
        return normalizer.codeforces_activity_normalizer(events)

    @staticmethod
    def sync_all_platforms(generation_request):
        user = generation_request.user

        platform_accounts = PlatformAccount.objects.filter(user=user)

        all_data = []
        # TODO: include all the platforms for syncing
        for account in platform_accounts:
            if account.platform == Platform.GITHUB:
                try:
                    data = SyncService.sync_github_data(account.username)
                    all_data.append((account, data))
                except Exception as e:
                    PlatformAccount.objects.filter(id=account.id).update(
                        last_fetched=timezone.now(), fetch_error=str(e)
                    )
            if account.platform == Platform.CODEFORCES:
                try:
                    data = SyncService.sync_codeforces_data(account.username)
                    all_data.append((account, data))
                except Exception as e:
                    PlatformAccount.objects.filter(id=account.id).update(
                        last_fetched=timezone.now(), fetch_error=str(e)
                    )
        with transaction.atomic():
            for account, normalized_events in all_data:
                ActivityService.bulk_save(
                    generation_request,
                    normalized_events,
                    platform=account.platform,
                )

                PlatformAccount.objects.filter(id=account.id).update(
                    last_fetched=timezone.now(),
                    fetch_error=None,
                )
            generation_request.status = "success"
            generation_request.save()
        with transaction.atomic():
            MetricsService.calculate_metrics(generation_request)
