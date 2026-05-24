from ..platforms import GitHubClient


github = GitHubClient()
summary = github.get_activity_summary("naga-ruthvik")
print(summary)
