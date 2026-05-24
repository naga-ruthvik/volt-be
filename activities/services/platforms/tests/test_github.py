import requests

from ..errors import (
    PlatformNetworkError,
    PlatformTimeoutError,
)
from ..github import GitHubClient


class DummyResponse:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


def test_get_user_info_success(mocker):
    response = DummyResponse(
        200,
        {
            "id": 123,
            "login": "octocat",
            "name": "Octo Cat",
            "created_at": "2024-05-01T12:00:00Z",
            "followers": 5,
            "following": 2,
            "public_repos": 3,
        },
    )
    mocker.patch(
        "activities.services.platforms.github.requests.get", return_value=response
    )

    client = GitHubClient(base_url="https://api.github.test")
    payload = client.get_user_info("octocat")

    assert payload == {
        "status": "success",
        "platform": "github",
        "username": "octocat",
        "data": {
            "id": "123",
            "platform": "github",
            "username": "octocat",
            "name": "Octo Cat",
            "created_at": "2024-05-01T12:00:00Z",
            "followers": 5,
            "following": 2,
            "public_repos": 3,
        },
    }


def test_get_events_success_with_fallback_id(mocker):
    responses = [
        DummyResponse(
            200,
            [
                {
                    "id": None,
                    "created_at": "2024-05-01T12:00:00Z",
                    "type": "PushEvent",
                    "repo": {"name": "octocat/hello"},
                    "actor": {"login": "octocat"},
                }
            ],
        ),
        DummyResponse(200, []),
    ]
    mocker.patch(
        "activities.services.platforms.github.requests.get",
        side_effect=responses,
    )

    client = GitHubClient(base_url="https://api.github.test")
    payload = client.get_events("octocat")

    assert payload["status"] == "success"
    assert payload["platform"] == "github"
    assert payload["username"] == "octocat"
    assert payload["data"][0]["platform"] == "github"
    assert payload["data"][0]["created_at"] == "2024-05-01T12:00:00Z"
    assert payload["data"][0]["id"]


def test_get_activity_summary_success(mocker):
    responses = [
        DummyResponse(
            200,
            [
                {"id": "1", "created_at": "2024-05-01T12:00:00Z", "type": "PushEvent"},
                {"id": "2", "created_at": "2024-05-01T13:00:00Z", "type": "PushEvent"},
            ],
        ),
        DummyResponse(200, []),
    ]
    mocker.patch(
        "activities.services.platforms.github.requests.get",
        side_effect=responses,
    )

    client = GitHubClient(base_url="https://api.github.test")
    payload = client.get_activity_summary("octocat")

    assert payload == {
        "status": "success",
        "platform": "github",
        "username": "octocat",
        "data": [{"platform": "github", "date": "2024-05-01", "count": 2}],
    }


def test_get_user_info_invalid_username(mocker):
    response = DummyResponse(404, {"message": "Not Found"})
    mocker.patch(
        "activities.services.platforms.github.requests.get", return_value=response
    )

    client = GitHubClient(base_url="https://api.github.test")
    payload = client.get_user_info("missing")

    assert payload == {
        "status": "error",
        "platform": "github",
        "error_type": "INVALID_USERNAME",
        "message": "GitHub user not found",
        "details": {},
    }


def test_get_events_rate_limit(mocker):
    response = DummyResponse(403, {"message": "API rate limit exceeded"})
    mocker.patch(
        "activities.services.platforms.github.requests.get", return_value=response
    )

    client = GitHubClient(base_url="https://api.github.test")
    payload = client.get_events("octocat")

    assert payload == {
        "status": "error",
        "platform": "github",
        "error_type": "RATE_LIMIT",
        "message": "GitHub rate limit exceeded",
        "details": {},
    }


def test_get_user_info_timeout(mocker):
    mocker.patch(
        "activities.services.platforms.github.requests.get",
        side_effect=requests.Timeout,
    )

    client = GitHubClient(base_url="https://api.github.test")
    try:
        client.get_user_info("octocat")
        assert False, "Expected PlatformTimeoutError"
    except PlatformTimeoutError:
        assert True


def test_get_repos_network_failure(mocker):
    mocker.patch(
        "activities.services.platforms.github.requests.get",
        side_effect=requests.RequestException,
    )

    client = GitHubClient(base_url="https://api.github.test")
    try:
        client.get_repos("octocat")
        assert False, "Expected PlatformNetworkError"
    except PlatformNetworkError:
        assert True
