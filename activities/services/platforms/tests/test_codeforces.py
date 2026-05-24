import requests

from ..codeforces import CodeforcesClient
from ..errors import (
    PlatformNetworkError,
    PlatformTimeoutError,
)


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
            "status": "OK",
            "result": [
                {
                    "handle": "tourist",
                    "firstName": "Gennady",
                    "registrationTimeSeconds": 1_600_000_000,
                    "rating": 3000,
                    "rank": "legendary grandmaster",
                }
            ],
        },
    )
    mocker.patch(
        "activities.services.platforms.codeforces.requests.get", return_value=response
    )

    client = CodeforcesClient(base_url="https://codeforces.test/api/")
    payload = client.get_user_info("tourist")

    assert payload["status"] == "success"
    assert payload["platform"] == "codeforces"
    assert payload["username"] == "tourist"
    assert payload["data"]["platform"] == "codeforces"
    assert payload["data"]["username"] == "tourist"
    assert payload["data"]["created_at"].startswith("2020-")


def test_get_activities_success(mocker):
    response = DummyResponse(
        200,
        {
            "status": "OK",
            "result": [
                {
                    "id": 99,
                    "creationTimeSeconds": 1_700_000_000,
                    "problem": {"name": "Two Sum"},
                    "verdict": "OK",
                }
            ],
        },
    )
    mocker.patch(
        "activities.services.platforms.codeforces.requests.get", return_value=response
    )

    client = CodeforcesClient(base_url="https://codeforces.test/api/")
    payload = client.get_activities("tourist")

    assert payload["status"] == "success"
    assert payload["platform"] == "codeforces"
    assert payload["username"] == "tourist"
    assert payload["data"][0]["id"] == "99"
    assert payload["data"][0]["platform"] == "codeforces"
    assert payload["data"][0]["event_type"] == "submission"


def test_get_activity_summary_success(mocker):
    response = DummyResponse(
        200,
        {
            "status": "OK",
            "result": [
                {"id": 1, "creationTimeSeconds": 1_700_000_000},
                {"id": 2, "creationTimeSeconds": 1_700_000_100},
            ],
        },
    )
    mocker.patch(
        "activities.services.platforms.codeforces.requests.get", return_value=response
    )

    client = CodeforcesClient(base_url="https://codeforces.test/api/")
    payload = client.get_activity_summary("tourist")

    assert payload == {
        "status": "success",
        "platform": "codeforces",
        "username": "tourist",
        "data": [
            {"platform": "codeforces", "date": payload["data"][0]["date"], "count": 2}
        ],
    }


def test_get_user_info_invalid_username(mocker):
    response = DummyResponse(
        200,
        {"status": "FAILED", "comment": "user with handle missing not found"},
    )
    mocker.patch(
        "activities.services.platforms.codeforces.requests.get", return_value=response
    )

    client = CodeforcesClient(base_url="https://codeforces.test/api/")
    payload = client.get_user_info("missing")

    assert payload == {
        "status": "error",
        "platform": "codeforces",
        "error_type": "INVALID_USERNAME",
        "message": "Codeforces user not found",
        "details": {},
    }


def test_get_activities_rate_limit(mocker):
    response = DummyResponse(
        200,
        {"status": "FAILED", "comment": "rate limit exceeded"},
    )
    mocker.patch(
        "activities.services.platforms.codeforces.requests.get", return_value=response
    )

    client = CodeforcesClient(base_url="https://codeforces.test/api/")
    payload = client.get_activities("tourist")

    assert payload == {
        "status": "error",
        "platform": "codeforces",
        "error_type": "RATE_LIMIT",
        "message": "Codeforces rate limit exceeded",
        "details": {},
    }


def test_get_user_info_timeout(mocker):
    mocker.patch(
        "activities.services.platforms.codeforces.requests.get",
        side_effect=requests.Timeout,
    )

    client = CodeforcesClient(base_url="https://codeforces.test/api/")
    try:
        client.get_user_info("tourist")
        assert False, "Expected PlatformTimeoutError"
    except PlatformTimeoutError:
        assert True


def test_get_activities_network_failure(mocker):
    mocker.patch(
        "activities.services.platforms.codeforces.requests.get",
        side_effect=requests.RequestException,
    )

    client = CodeforcesClient(base_url="https://codeforces.test/api/")
    try:
        client.get_activities("tourist")
        assert False, "Expected PlatformNetworkError"
    except PlatformNetworkError:
        assert True
