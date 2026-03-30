# normalize all the response we get from platforms APIs
class ActivityNormalization:
    def github_activity_normalizer(self, events):
        activity_map = {}
        for event in events:
            date = event["created_at"][:10]
            activity_map[date] = activity_map.get(date, 0) + 1
        return activity_map
