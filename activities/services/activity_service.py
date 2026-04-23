from datetime import datetime
from django.db import IntegrityError
from activities.models import Activity


class ActivityService:
    @staticmethod
    def bulk_save(generation_request, normalized_events, platform):
        if platform is None:
            raise ValueError("Platform cannot be None")

        activities = []

        for activity_date, activity_count in normalized_events.items():
            date_obj = datetime.strptime(str(activity_date), "%Y-%m-%d").date()

            activities.append(
                Activity(
                    generation_request=generation_request,
                    platform=platform,
                    activity_date=date_obj,
                    activity_count=activity_count,
                )
            )

        Activity.objects.bulk_create(activities, ignore_conflicts=True)
