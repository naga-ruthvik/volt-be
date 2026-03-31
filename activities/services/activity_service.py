from datetime import datetime

from activities.models import Activity


class ActivityService:
    @staticmethod
    def bulk_save(generation_request, normalized_events, platform):
        if platform is None:
            raise Exception("Platform cannot be None")
        activities = []
        for activity_date, activity_count in normalized_events.items():
            date_obj = datetime.strptime(str(activity_date), "%Y-%m-%d").date()
            activity = Activity(
                generation_request=generation_request,
                platform=platform,
                activity_date=date_obj,
                activity_count=activity_count,
            )
            activities.append(activity)
        Activity.objects.bulk_create(activities)
