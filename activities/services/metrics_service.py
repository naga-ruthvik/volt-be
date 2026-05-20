from datetime import timedelta

from django.db.models import Sum
from django.utils import timezone

from activities.models import (
    Activity,
    GenerationRequest,
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
                "total_active_days": 0,
                "current_streak": 0,
                "longest_streak": 0,
                "total_activities": 0,
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
        total_activities = sum(day_summary["total_count"] or 0 for day_summary in daily_totals)
        metrics = {
            "total_active_days": len(active_dates),
            "current_streak": current_streak,
            "longest_streak": longest_streak,
            "total_activities": total_activities,
        }
        GenerationRequest.objects.filter(id=generation_request.id).update(**metrics)
        return metrics

    @staticmethod
    def _user_metrics(generation_request):
        user = generation_request.user
        user_metrics, _ = UserMetrics.objects.get_or_create(user=user)

        all_user_activities = Activity.objects.filter(generation_request__user=user).order_by(
            "platform",
            "activity_date",
            "generation_request__created_at",
            "id",
        )

        latest_platform_daily_counts = {}
        for activity in all_user_activities:
            latest_platform_daily_counts[(activity.platform, activity.activity_date)] = (
                activity.activity_count
            )

        daily_totals = {}
        for (_, activity_date), activity_count in latest_platform_daily_counts.items():
            daily_totals[activity_date] = daily_totals.get(activity_date, 0) + activity_count

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
    def calculate_metrics(generation_request):
        generation_metrics = MetricsService._generation_metrics(generation_request)
        user_metrics = MetricsService._user_metrics(generation_request)
        return {
            "generation_metrics": generation_metrics,
            "user_metrics": user_metrics,
        }
