from datetime import datetime
from activities.models import Activity


class ActivityService:
    @staticmethod
    def bulk_save(generation_request, normalized_events, platform=None):
        if normalized_events is None:
            raise ValueError("Normalized events cannot be None")

        user = generation_request.user

        for entry in normalized_events:
            activity_date = entry.get("date")
            activity_count = entry.get("count")
            entry_platform = platform or entry.get("platform")
            if entry_platform is None:
                raise ValueError("Platform cannot be None")
            if activity_date is None or activity_count is None:
                continue

            date_obj = datetime.strptime(str(activity_date), "%Y-%m-%d").date()

            Activity.objects.update_or_create(
                user=user,
                platform=entry_platform,
                activity_date=date_obj,
                defaults={
                    "generation_request": generation_request,
                    "activity_count": activity_count,
                },
            )
