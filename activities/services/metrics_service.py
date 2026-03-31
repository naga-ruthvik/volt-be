from datetime import date, timedelta

from django.db.models import Sum

from activities.models import Activity, GenerationRequest


class MetricsService:
    @staticmethod
    def calculate_metrics(generation_request):
        activities = Activity.objects.filter(generation_request=generation_request)
        if not activities.exists():
            return {
                "total_active_days": 0,
                "current_streak": 0,
                "longest_streak": 0,
                "total_activities": 0,
            }
        total_active_days = activities.filter(activity_count__gt=0).count()
        total_activities = activities.aggregate(total=Sum("activity_count"))["total"]
        sorted_activities = activities.order_by("activity_date")
        current_streak = 0
        longest_streak = 0
        temp_streak = 0
        prev_date = None

        for activity in sorted_activities:
            if activity.activity_count > 0:
                if prev_date is None:
                    # First activity
                    temp_streak = 1
                elif (activity.activity_date - prev_date).days == 1:
                    # Consecutive day
                    temp_streak += 1
                else:
                    # Gap in dates - streak broken
                    temp_streak = 1

                longest_streak = max(longest_streak, temp_streak)
                prev_date = activity.activity_date
            else:
                # No activity on this day - only breaks streak if date is consecutive
                if prev_date and (activity.activity_date - prev_date).days == 1:
                    temp_streak = 0
                prev_date = activity.activity_date

        # Calculate current streak (must extend to today or yesterday)
        today = date.today()
        if prev_date and prev_date >= today - timedelta(days=1):
            current_streak = temp_streak
        else:
            current_streak = 0
        GenerationRequest.objects.filter(id=generation_request.id).update(
            total_activities=total_activities,
            total_active_days=total_active_days,
            current_streak=current_streak,
            longest_streak=longest_streak,
        )
        return {
            "total_active_days": total_active_days,
            "current_streak": current_streak,
            "longest_streak": longest_streak,
            "total_activities": total_activities,
        }
