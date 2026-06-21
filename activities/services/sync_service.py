import json
from datetime import datetime
from datetime import timezone as dt_timezone
from importlib.metadata import metadata

from django.db import transaction
from django.utils import timezone

from asgiref.sync import async_to_sync

from activities.models import Platform, PlatformAccount
from activities.services.activity_service import ActivityService
from activities.services.metrics_service import MetricsService
from activities.services.platforms import (
    CodeChefScraper,
    CodeforcesClient,
    GitHubClient,
    HackerRankClient,
    LeetcodeClient,
)


class SyncService:
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
        contest_info = leetcode_client.get_user_contest_ranking_info(username).get(
            "data", {}
        )
        if SyncService._is_error_payload(profile_payload):
            return profile_payload

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
                "data": [],
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
        data = {}
        data["activity_summary"] = normalized
        data["metadata"] = leetcode_metadata
        normalized.sort(key=lambda item: item.get("date") or "")
        return {
            "status": "success",
            "platform": "leetcode",
            "username": username,
            "data": data,
        }

    @staticmethod
    def sync_hackerrank(username: str):
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
    def sync_codechef(username: str):
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
        leetcode_metadata = {}
        leetcode_metadata["username"] = profile_data["username"]
        leetcode_metadata["name"] = profile_data["name"]
        leetcode_metadata["avatar"] = profile_data["avatar"]
        leetcode_metadata["star_rating"] = profile_data["star_rating"]
        leetcode_metadata["contributions"] = profile_data["contributions"]
        leetcode_metadata["badges"] = profile_data["badges"]
        total_submit_stats = profile_data["submit_stats"]["total"]
        accepted_submit_stats = profile_data["submit_stats"]["accepted"]
        submit_stats = {}
        for stat in total_submit_stats:
            submit_stats[stat["difficulty"]] = {"total": stat["count"]}
        for stat in accepted_submit_stats:
            submit_stats[stat["difficulty"]]["accepted"] = stat["count"]
        leetcode_metadata["submit_stats"] = submit_stats
        return leetcode_metadata

    @staticmethod
    def sync_all_platforms(generation_request):
        user = generation_request.user
        platform_accounts = PlatformAccount.objects.filter(user=user)

        all_data = []
        hackerank_resp = {}
        codechef_metrics = {}

        # TODO: include all the platforms for syncing
        for account in platform_accounts:
            if account.platform == Platform.GITHUB:
                data = SyncService.sync_github_data(account.username)
                if SyncService._is_error_payload(data):
                    PlatformAccount.objects.filter(id=account.id).update(
                        last_fetched=timezone.now(), fetch_error=data.get("message")
                    )
                    continue
                all_data.append((account, SyncService._unwrap_success(data)))
            if account.platform == Platform.CODEFORCES:
                data = SyncService.sync_codeforces_data(account.username)
                if SyncService._is_error_payload(data):
                    PlatformAccount.objects.filter(id=account.id).update(
                        last_fetched=timezone.now(), fetch_error=data.get("message")
                    )
                    continue
                all_data.append((account, SyncService._unwrap_success(data)))

            if account.platform == Platform.LEETCODE:
                data = SyncService.sync_leetcode_data(account.username)
                if SyncService._is_error_payload(data):
                    PlatformAccount.objects.filter(id=account.id).update(
                        last_fetched=timezone.now(), fetch_error=data.get("message")
                    )
                    continue
                leetcode_metadata = data.get("data", {}).get("metadata", {})
                activity_summary = data.get("data", {}).get("activity_summary", [])
                all_data.append(
                    (account, SyncService._unwrap_success(activity_summary))
                )

            if account.platform == Platform.HACKERRANK:
                # hackerrank doesn't have option to get the activities so just fill the metadata
                hackerank_resp = SyncService.sync_hackerrank(account.username)
                if SyncService._is_error_payload(hackerank_resp):
                    PlatformAccount.objects.filter(id=account.id).update(
                        last_fetched=timezone.now(),
                        fetch_error=hackerank_resp.get("message"),
                    )

            if account.platform == Platform.CODECHEF:
                codechef_data = SyncService.sync_codechef(account.username)
                if SyncService._is_error_payload(codechef_data):
                    PlatformAccount.objects.filter(id=account.id).update(
                        last_fetched=timezone.now(),
                        fetch_error=codechef_data.get("message"),
                    )
                codechef_metrics = codechef_data.get("data", {}).get("profile", {})
                heatmap_data = codechef_data.get("data", {}).get("heatmap", [])
                all_data.append((account, heatmap_data))

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
            generation_request.status = "completed"
            generation_request.last_synced_at = timezone.now()
            generation_request.save(update_fields=["status", "last_synced_at"])

            # update hackerrank metadata
            hackerrank_metrics_data = hackerank_resp.get("data", {})
            PlatformAccount.objects.filter(
                user=user, platform=Platform.HACKERRANK
            ).update(metadata=hackerrank_metrics_data)

            PlatformAccount.objects.filter(
                user=user, platform=Platform.CODECHEF
            ).update(metadata=codechef_metrics)
            PlatformAccount.objects.filter(
                user=user, platform=Platform.LEETCODE
            ).update(metadata=leetcode_metadata)

        with transaction.atomic():
            MetricsService.calculate_metrics(generation_request)
