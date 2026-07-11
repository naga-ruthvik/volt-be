import json
import logging
from datetime import datetime
from datetime import timezone as dt_timezone

from django.db import transaction
from django.utils import timezone

from asgiref.sync import async_to_sync

from activities.models import Platform, PlatformAccount, UserMetrics
from activities.services.activity_service import ActivityService
from activities.services.metrics_service import MetricsService
from activities.services.platforms import (
    CodeChefScraper,
    CodeforcesClient,
    GitHubClient,
    HackerRankClient,
    LeetcodeClient,
)

logger = logging.getLogger(__name__)


class SyncService:
    # ------------------------------------------------------------------ #
    # Public per-platform fetch methods                                   #
    # ------------------------------------------------------------------ #

    @staticmethod
    def sync_github_data(username):
        github_client = GitHubClient()
        return github_client.get_activity_summary(username)

    @staticmethod
    def sync_codeforces_data(username):
        codeforces_client = CodeforcesClient()
        return codeforces_client.get_activity_summary(username)

    @staticmethod
    def sync_leetcode_data(username):
        leetcode_client = LeetcodeClient()
        profile_payload = leetcode_client.get_user_profile(username)

        # Check the profile before making any further API calls.
        if SyncService._is_error_payload(profile_payload):
            return profile_payload
        try:
            contest_raw = leetcode_client.get_user_contest_ranking_info(username)
            contest_info = contest_raw.get("data", {})
        except Exception:
            logger.warning(
                "Failed to fetch LeetCode contest ranking for '%s'; skipping.",
                username,
            )
            contest_info = {}

        leetcode_profile_data = profile_payload.get("data", {})
        submission_calendar = leetcode_profile_data.get("submission_calendar")
        leetcode_metadata = SyncService._get_leetcode_profile_metadata(
            leetcode_profile_data
        )
        leetcode_metadata["contest"] = contest_info
        if not submission_calendar:
            return {
                "status": "success",
                "platform": "leetcode",
                "username": username,
                "data": {"activity_summary": [], "metadata": leetcode_metadata},
            }

        try:
            calendar_map = json.loads(submission_calendar)
        except (TypeError, ValueError):
            return {
                "status": "error",
                "platform": "leetcode",
                "error_type": "INVALID_CALENDAR",
                "message": "[LeetCode] API Error: Invalid submission calendar.",
                "details": {"username": username},
            }

        normalized = []
        for timestamp_str, count in calendar_map.items():
            try:
                ts_int = int(timestamp_str)
            except (TypeError, ValueError):
                continue
            date = datetime.fromtimestamp(ts_int, tz=dt_timezone.utc).date().isoformat()
            normalized.append(
                {
                    "platform": "leetcode",
                    "date": date,
                    "count": int(count),
                }
            )

        normalized.sort(key=lambda item: item.get("date") or "")

        return {
            "status": "success",
            "platform": "leetcode",
            "username": username,
            "data": {
                "activity_summary": normalized,
                "metadata": leetcode_metadata,
            },
        }

    @staticmethod
    def sync_hackerrank_data(username: str):
        client = HackerRankClient()
        user_info = client.get_user_info(username)
        if SyncService._is_error_payload(user_info):
            return user_info
        metrics = client.get_user_metrics(username)
        if SyncService._is_error_payload(metrics):
            return metrics
        return {
            "status": "success",
            "platform": "hackerrank",
            "username": username,
            "data": metrics.get("data", {}),
        }

    @staticmethod
    def sync_codechef_data(username: str):
        client = CodeChefScraper()
        codechef_response = async_to_sync(client.scrape_user_profile)(username)
        if SyncService._is_error_payload(codechef_response):
            return codechef_response
        return {
            "status": "success",
            "platform": "codechef",
            "username": username,
            "data": codechef_response.get("data", {}),
        }

    # ------------------------------------------------------------------ #
    # Orchestration                                                        #
    # ------------------------------------------------------------------ #

    @staticmethod
    def sync_all_platforms(generation_request):
        user = generation_request.user
        platform_accounts = PlatformAccount.objects.filter(user=user)

        all_data, platform_metadata = SyncService._fetch_all_platform_data(
            platform_accounts
        )
        cumulative_metrics = MetricsService.calculate_cumulative_platform_metrics(
            platform_metadata
        )
        with transaction.atomic():
            SyncService._persist_activity_data(generation_request, all_data)
            SyncService._persist_metadata(user, generation_request, platform_metadata)
            activity_metrics = MetricsService.calculate_activity_metrics(
                generation_request
            )
            SyncService._persist_metrics_data(
                user, activity_metrics.get("user_metrics", {}), cumulative_metrics
            )

    # ------------------------------------------------------------------ #
    # Private helpers                                                      #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _fetch_all_platform_data(platform_accounts):
        """
        Iterate over a user's linked accounts and fetch raw data from each
        platform client.

        Returns:
            all_data        – list of (account, normalized_events) tuples ready
                              for bulk_save.
            platform_metadata – dict of per-platform metadata keyed by Platform
                              value (e.g. "leetcode", "hackerrank", "codechef").
        """
        all_data = []
        # Keyed by Platform value string; populated only when a platform
        # successfully returns metadata worth storing on PlatformAccount.
        platform_metadata = {}

        for account in platform_accounts:
            # Wrap each platform sync in try/except so a network error or
            # unexpected response shape from one platform is isolated to that
            # account — it won't abort the remaining platforms in the batch.
            try:
                if account.platform == Platform.GITHUB:
                    data = SyncService.sync_github_data(account.username)
                    if SyncService._is_error_payload(data):
                        SyncService._mark_account_error(account, data.get("message"))
                        continue
                    all_data.append((account, SyncService._unwrap_success(data)))

                elif account.platform == Platform.CODEFORCES:
                    data = SyncService.sync_codeforces_data(account.username)
                    if SyncService._is_error_payload(data):
                        SyncService._mark_account_error(account, data.get("message"))
                        continue
                    all_data.append((account, SyncService._unwrap_success(data)))

                elif account.platform == Platform.LEETCODE:
                    data = SyncService.sync_leetcode_data(account.username)
                    if SyncService._is_error_payload(data):
                        SyncService._mark_account_error(account, data.get("message"))
                        continue
                    inner = data.get("data", {})
                    all_data.append((account, inner.get("activity_summary", [])))
                    platform_metadata[Platform.LEETCODE] = inner.get("metadata", {})

                elif account.platform == Platform.HACKERRANK:
                    # HackerRank has no public activity timeline, so we only
                    # capture metadata (questions solved, badges, etc.).
                    hackerrank_resp = SyncService.sync_hackerrank_data(account.username)
                    if SyncService._is_error_payload(hackerrank_resp):
                        SyncService._mark_account_error(
                            account, hackerrank_resp.get("message")
                        )
                        continue
                    platform_metadata[Platform.HACKERRANK] = hackerrank_resp.get(
                        "data", {}
                    )

                elif account.platform == Platform.CODECHEF:
                    codechef_data = SyncService.sync_codechef_data(account.username)
                    if SyncService._is_error_payload(codechef_data):
                        SyncService._mark_account_error(
                            account, codechef_data.get("message")
                        )
                        continue
                    inner = codechef_data.get("data", {})
                    platform_metadata[Platform.CODECHEF] = inner.get("profile", {})
                    all_data.append((account, inner.get("heatmap", [])))

            except Exception as exc:
                logger.exception(
                    "Unexpected error syncing %s account '%s': %s",
                    account.platform,
                    account.username,
                    exc,
                )
                SyncService._mark_account_error(account, str(exc))

        return all_data, platform_metadata

    @staticmethod
    def _persist_activity_data(generation_request, all_data):
        """Bulk-save activity rows and mark each account as successfully synced."""
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

    @staticmethod
    def _persist_metadata(user, generation_request, platform_metadata):
        """
        Write per-platform metadata back to PlatformAccount rows and mark the
        GenerationRequest as completed.

        Only updates rows for platforms that actually returned metadata this
        run — platforms with no data (e.g. not linked, or errored) are left
        untouched.
        """
        generation_request.status = "completed"
        generation_request.last_synced_at = timezone.now()
        generation_request.save(update_fields=["status", "last_synced_at"])

        if Platform.HACKERRANK in platform_metadata:
            PlatformAccount.objects.filter(
                user=user, platform=Platform.HACKERRANK
            ).update(metadata=platform_metadata[Platform.HACKERRANK])

        if Platform.CODECHEF in platform_metadata:
            PlatformAccount.objects.filter(
                user=user, platform=Platform.CODECHEF
            ).update(metadata=platform_metadata[Platform.CODECHEF])

        if Platform.LEETCODE in platform_metadata:
            PlatformAccount.objects.filter(
                user=user, platform=Platform.LEETCODE
            ).update(metadata=platform_metadata[Platform.LEETCODE])

    @staticmethod
    def _persist_metrics_data(user, activity_metrics, cumulative_metrics):
        """
        Persist calculated metrics to the UserMetrics model.

        Args:
            user: The user instance to update metrics for.
            activity_metrics: Dict containing activity-based metrics (streaks, active days, etc.).
            cumulative_metrics: Dict containing platform-aggregated metrics (questions solved, contests, etc.).
        """
        # activity metrics
        total_active_days = activity_metrics.get("total_active_days", 0)
        current_streak = activity_metrics.get("current_streak", 0)
        longest_streak = activity_metrics.get("longest_streak", 0)
        total_activities = activity_metrics.get("total_activities", 0)

        # cumulative platform metrics
        total_questions_solved = cumulative_metrics.get("total_questions_solved", 0)
        easy_questions_solved = cumulative_metrics.get("total_easy_questions_solved", 0)
        medium_questions_solved = cumulative_metrics.get(
            "total_medium_questions_solved", 0
        )
        hard_questions_solved = cumulative_metrics.get("total_hard_questions_solved", 0)
        total_contests = cumulative_metrics.get("total_contests", 0)

        UserMetrics.objects.filter(user=user).update(
            total_active_days=total_active_days,
            current_streak=current_streak,
            total_activities=total_activities,
            longest_streak=longest_streak,
            total_contests=total_contests,
            total_questions_solved=total_questions_solved,
            easy_questions_solved=easy_questions_solved,
            medium_questions_solved=medium_questions_solved,
            hard_questions_solved=hard_questions_solved,
        )

    @staticmethod
    def _mark_account_error(account, message: str):
        """Record a fetch failure on a PlatformAccount without raising."""
        logger.warning(
            "Sync failed for %s account '%s': %s",
            account.platform,
            account.username,
            message,
        )
        PlatformAccount.objects.filter(id=account.id).update(
            last_fetched=timezone.now(),
            fetch_error=message,
        )

    @staticmethod
    def _is_error_payload(data) -> bool:
        return isinstance(data, dict) and data.get("status") == "error"

    @staticmethod
    def _unwrap_success(data):
        if isinstance(data, dict) and data.get("status") == "success":
            return data.get("data", [])
        return data

    @staticmethod
    def _get_leetcode_profile_metadata(profile_data):
        submit_stats = {}
        for stat in profile_data.get("submit_stats", {}).get("total", []):
            difficulty = stat.get("difficulty")
            if difficulty is not None:
                submit_stats[difficulty] = {"total": stat.get("count", 0)}
        for stat in profile_data.get("submit_stats", {}).get("accepted", []):
            difficulty = stat.get("difficulty")
            if difficulty in submit_stats:
                submit_stats[difficulty]["accepted"] = stat.get("count", 0)

        return {
            "username": profile_data.get("username"),
            "name": profile_data.get("name"),
            "avatar": profile_data.get("avatar"),
            "star_rating": profile_data.get("star_rating"),
            "contributions": profile_data.get("contributions"),
            "badges": profile_data.get("badges", []),
            "submit_stats": submit_stats,
        }
