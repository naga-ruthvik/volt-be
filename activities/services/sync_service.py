from datetime import datetime

from app.activities.models import GenerationRequest, Platform, PlatformAccount
from app.activities.services.normalization import ActivityNormalization
from app.activities.services.platforms.github_service import GitHubService


class SyncService:
    """
    service that syncs the normalised data to the database, also handles error management
    and updating the last fetched time for each platform account
    fetch data -> normalise data -> save to db -> update last fetched time and error status
    """

    @staticmethod
    def sync_github(generation_request, username):
        try:
            github_service = GitHubService()
            normalization_service = ActivityNormalization()
            events = github_service.fetch_events(username)
            normalized_events = normalization_service.github_activity_normalizer(events)
            generation_request.bulk_create(normalized_events)
            platform_account = PlatformAccount.objects.filter(
                username=username,
                platform=Platform.GITHUB,
                user=generation_request.user,
            ).first()
            platform_account.last_fetched = datetime.now()
            platform_account.fetch_error = None
            platform_account.save()
            return normalized_events
        except Exception as e:
            PlatformAccount.objects.filter(
                username=username,
                platform=Platform.GITHUB,
                user=generation_request.user,
            ).update(last_fetched=datetime.now(), fetch_error=str(e))

            raise e

    @staticmethod
    def sync_leetcode(generation_request, username):
        pass
