# normalize all the response we get from platforms APIs
from datetime import datetime, timezone


class ActivityNormalization:
    def github_activity_normalizer(self, events):
        activity_map = {}
        for event in events:
            date = event["created_at"][:10]
            activity_map[date] = activity_map.get(date, 0) + 1
        return activity_map

    def codeforces_activity_normalizer(self, events):
        activity_map = {}

        for event in events.get("result", []):
            timestamp = event.get("creationTimeSeconds")

            if not timestamp:
                continue

            date = datetime.fromtimestamp(timestamp, tz=timezone.utc).strftime(
                "%Y-%m-%d"
            )

            activity_map[date] = activity_map.get(date, 0) + 1

        return activity_map
