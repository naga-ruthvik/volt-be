from datetime import timedelta

from django.db.models import Sum
from django.utils import timezone

from activities.models import (
    Activity,
    GenerationRequest,
    Platform,
    PlatformAccount,
    UserMetrics,
)


class MetricsService:
    @staticmethod
    def _calculate_streaks(active_dates):
        if not active_dates:
            return 0, 0

        longest_streak = 1
        running_streak = 1
        for idx in range(1, len(active_dates)):
            if (active_dates[idx] - active_dates[idx - 1]).days == 1:
                running_streak += 1
            else:
                running_streak = 1
            longest_streak = max(longest_streak, running_streak)

        current_streak = 0
        today = timezone.localdate()
        if active_dates[-1] >= today - timedelta(days=1):
            current_streak = 1
            for idx in range(len(active_dates) - 2, -1, -1):
                if (active_dates[idx + 1] - active_dates[idx]).days == 1:
                    current_streak += 1
                else:
                    break

        return current_streak, longest_streak

    @staticmethod
    def _generation_metrics(generation_request):
        activities = Activity.objects.filter(generation_request=generation_request)
        if not activities.exists():
            metrics = {
                "gen_active_days": 0,
                "gen_longest_streak": 0,
                "gen_total_activities": 0,
            }
            GenerationRequest.objects.filter(id=generation_request.id).update(**metrics)
            return metrics

        daily_totals = list(
            activities.values("activity_date")
            .annotate(total_count=Sum("activity_count"))
            .order_by("activity_date")
        )
        active_dates = [
            day_summary["activity_date"]
            for day_summary in daily_totals
            if (day_summary["total_count"] or 0) > 0
        ]
        current_streak, longest_streak = MetricsService._calculate_streaks(active_dates)
        total_activities = sum(
            day_summary["total_count"] or 0 for day_summary in daily_totals
        )
        metrics = {
            "gen_active_days": len(active_dates),
            "gen_longest_streak": longest_streak,
            "gen_total_activities": total_activities,
        }
        GenerationRequest.objects.filter(id=generation_request.id).update(**metrics)
        return metrics

    @staticmethod
    def _user_metrics(generation_request):
        user = generation_request.user
        user_metrics, _ = UserMetrics.objects.get_or_create(user=user)

        daily_totals = {}
        for activity in Activity.objects.filter(user=user).order_by(
            "activity_date", "id"
        ):
            daily_totals[activity.activity_date] = (
                daily_totals.get(activity.activity_date, 0) + activity.activity_count
            )

        total_activities = sum(daily_totals.values())
        sorted_days = sorted(daily_totals.keys())
        active_dates = [
            activity_date
            for activity_date in sorted_days
            if daily_totals[activity_date] > 0
        ]
        current_streak, longest_streak = MetricsService._calculate_streaks(active_dates)

        user_metrics.total_activities = total_activities
        user_metrics.total_active_days = len(active_dates)
        user_metrics.current_streak = current_streak
        user_metrics.longest_streak = longest_streak
        user_metrics.save(
            update_fields=[
                "total_activities",
                "total_active_days",
                "current_streak",
                "longest_streak",
                "updated_at",
            ]
        )

        return {
            "total_active_days": user_metrics.total_active_days,
            "current_streak": user_metrics.current_streak,
            "longest_streak": user_metrics.longest_streak,
            "total_activities": user_metrics.total_activities,
        }

    @staticmethod
    def calculate_activity_metrics(generation_request):
        generation_metrics = MetricsService._generation_metrics(generation_request)
        user_metrics = MetricsService._user_metrics(generation_request)
        return {
            "generation_metrics": generation_metrics,
            "user_metrics": user_metrics,
        }

    @staticmethod
    def get_platform_metadata(user):
        platforms_metadata = PlatformAccount.objects.filter(user=user).values(
            "platform", "metadata"
        )
        platform_data = {}
        for entry in platforms_metadata:
            platform_data[entry["platform"]] = entry["metadata"]
        return platform_data

    @staticmethod
    def calculate_cumulative_platform_metrics(platform_metrics: list) -> dict[str, int]:
        cumulative_metrics = {
            "total_questions_solved": 0,
            "total_easy_questions_solved": 0,
            "total_medium_questions_solved": 0,
            "total_hard_questions_solved": 0,
            "total_contests": 0,
        }
        # platform_metrics is expected to be a dict keyed by platform value
        # (e.g. "leetcode", "codechef") with the platform-specific metadata
        # as the value. Iterate items and accumulate safely.
        for platform, pdata in (platform_metrics or {}).items():
            if platform == Platform.LEETCODE:
                leetcode = pdata or {}
                submit_stats = leetcode.get("submit_stats", {})
                cumulative_metrics["total_questions_solved"] += (
                    submit_stats.get("All", {}).get("accepted", 0)
                )
                cumulative_metrics["total_easy_questions_solved"] += (
                    submit_stats.get("Easy", {}).get("accepted", 0)
                )
                cumulative_metrics["total_medium_questions_solved"] += (
                    submit_stats.get("Medium", {}).get("accepted", 0)
                )
                cumulative_metrics["total_hard_questions_solved"] += (
                    submit_stats.get("Hard", {}).get("accepted", 0)
                )
                cumulative_metrics["total_contests"] += len(
                    leetcode.get("contests", {}).get("history", [])
                )

            elif platform == Platform.CODECHEF:
                codechef = pdata or {}
                cumulative_metrics["total_questions_solved"] += codechef.get(
                    "totalSolved", 0
                )
                cumulative_metrics["total_contests"] += len(
                    codechef.get("ratingHistory", [])
                )

            elif platform == Platform.HACKERRANK:
                hackerrank = pdata or {}
                cumulative_metrics["total_questions_solved"] += hackerrank.get(
                    "questions_solved", 0
                )

        return cumulative_metrics
