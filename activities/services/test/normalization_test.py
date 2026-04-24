from ..platforms.github_service import GitHubService

from ..normalization import ActivityNormalization

github = GitHubService()
events = github.fetch_events("naga-ruthvik")
normalizer = ActivityNormalization()
activity_map = normalizer.github_activity_normalizer(events)
print(activity_map)
