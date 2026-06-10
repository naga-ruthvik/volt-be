"""GitHub client with normalized outputs and standardized error payloads.

Grouped summaries return: {"status": "success", "platform": "github", "username": str, "data": [{"date": "YYYY-MM-DD", "count": int, "platform": "github"}]}
Item lists return: {"status": "success", "platform": "github", "username": str, "data": [{"id": str, "platform": "github", "created_at": str, ...}]}
"""

import hashlib
import os

import requests
from dotenv import load_dotenv

from .errors import PlatformNetworkError, PlatformTimeoutError

load_dotenv()

GITHUB_API = os.getenv("GITHUB_API")


def _error_payload(platform: str, error_type: str, message: str, details=None) -> dict:
    return {
        "status": "error",
        "platform": "GITHUB",
        "error_type": error_type,
        "message": message,
        "details": details or {},
    }


def _build_fallback_id(
    platform: str, username: str, timestamp: str, event_type: str
) -> str:
    input_str = f"{platform}_{username}_{timestamp}_{event_type}"
    return hashlib.md5(input_str.encode("utf-8")).hexdigest()


def _success_payload(username: str, data) -> dict:
    return {
        "status": "success",
        "platform": "GITHUB",
        "username": username,
        "data": data,
    }


class GitHubClient:
    def __init__(self, base_url: str | None = None, timeout: tuple[int, int] = (5, 10)):
        self.base_url = base_url or GITHUB_API
        self.timeout = timeout

    def _get(self, url: str, params: dict | None = None) -> requests.Response:
        try:
            response = requests.get(url, params=params, timeout=self.timeout)
        except requests.Timeout as exc:
            raise PlatformTimeoutError("GitHub request timed out") from exc
        except requests.RequestException as exc:
            raise PlatformNetworkError("GitHub request failed") from exc

        if response.status_code >= 500:
            raise PlatformNetworkError("GitHub server error")

        return response

    def _is_rate_limited(self, response: requests.Response) -> bool:
        try:
            payload = response.json()
        except ValueError:
            return False

        if not isinstance(payload, dict):
            return False

        message = payload.get("message", "")
        return response.status_code == 403 and "rate limit" in message.lower()

    def get_user_info(self, username: str) -> dict:
        response = self._get(f"{self.base_url}/users/{username}")

        if response.status_code == 404:
            return _error_payload("github", "INVALID_USERNAME", "GitHub user not found")
        if self._is_rate_limited(response):
            return _error_payload("github", "RATE_LIMIT", "GitHub rate limit exceeded")
        if response.status_code != 200:
            return _error_payload("github", "UNKNOWN", "GitHub user fetch failed")

        data = response.json()
        normalized = {
            "id": str(data.get("id")) if data.get("id") is not None else None,
            "platform": "github",
            "username": data.get("login"),
            "name": data.get("name"),
            "created_at": data.get("created_at"),
            "followers": data.get("followers"),
            "following": data.get("following"),
            "public_repos": data.get("public_repos"),
        }
        return _success_payload("github", username, normalized)

    def get_user_exists(self, username: str) -> bool:
        response = self._get(f"{self.base_url}/users/{username}")
        return response.status_code == 200

    def get_events(self, username: str) -> list[dict] | dict:
        events = []

        for page in range(1, 4):
            response = self._get(
                f"{self.base_url}/users/{username}/events/public",
                params={"per_page": 100, "page": page},
            )

            if response.status_code == 404:
                return _error_payload(
                    "github", "INVALID_USERNAME", "GitHub user not found"
                )
            if self._is_rate_limited(response):
                return _error_payload(
                    "github", "RATE_LIMIT", "GitHub rate limit exceeded"
                )
            if response.status_code != 200:
                return _error_payload("github", "UNKNOWN", "GitHub events fetch failed")

            data = response.json()
            if not data:
                break

            events.extend(data)

        normalized = []
        for event in events:
            created_at = event.get("created_at")
            event_type = event.get("type", "event")
            event_id = event.get("id")
            if not event_id and created_at:
                event_id = _build_fallback_id(
                    "github", username, created_at, event_type
                )

            normalized.append(
                {
                    "id": str(event_id) if event_id is not None else None,
                    "platform": "github",
                    "created_at": created_at,
                    "event_type": event_type,
                    "repo_name": event.get("repo", {}).get("name"),
                    "actor": event.get("actor", {}).get("login"),
                }
            )

        return _success_payload("github", username, normalized)

    def get_activity_summary(self, username: str) -> list[dict] | dict:
        events_payload = self.get_events(username)
        if isinstance(events_payload, dict) and events_payload.get("status") == "error":
            return events_payload

        events = events_payload.get("data", [])
        activity_map = {}
        for event in events:
            created_at = event.get("created_at")
            if not created_at:
                continue
            date = created_at[:10]
            activity_map[date] = activity_map.get(date, 0) + 1

        summary = [
            {"platform": "github", "date": date, "count": count}
            for date, count in sorted(activity_map.items())
        ]
        return _success_payload("github", username, summary)

    def get_repos(self, username: str) -> list[dict] | dict:
        response = self._get(f"{self.base_url}/users/{username}/repos")

        if response.status_code == 404:
            return _error_payload("github", "INVALID_USERNAME", "GitHub user not found")
        if self._is_rate_limited(response):
            return _error_payload("github", "RATE_LIMIT", "GitHub rate limit exceeded")
        if response.status_code != 200:
            return _error_payload("github", "UNKNOWN", "GitHub repos fetch failed")

        repos = []
        for repo in response.json():
            repo_id = repo.get("id")
            created_at = repo.get("created_at")
            if not repo_id and created_at:
                repo_id = _build_fallback_id("github", username, created_at, "repo")

            repos.append(
                {
                    "id": str(repo_id) if repo_id is not None else None,
                    "platform": "github",
                    "name": repo.get("name"),
                    "full_name": repo.get("full_name"),
                    "created_at": created_at,
                    "updated_at": repo.get("updated_at"),
                    "is_private": repo.get("private"),
                }
            )

        return _success_payload("github", username, repos)
