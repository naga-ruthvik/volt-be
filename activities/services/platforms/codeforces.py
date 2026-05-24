"""Codeforces client with normalized outputs and standardized error payloads.

Grouped summaries return: {"status": "success", "platform": "codeforces", "username": str, "data": [{"date": "YYYY-MM-DD", "count": int, "platform": "codeforces"}]}
Item lists return: {"status": "success", "platform": "codeforces", "username": str, "data": [{"id": str, "platform": "codeforces", "created_at": str, ...}]}
"""

import hashlib
import os
from datetime import datetime, timezone

import requests
from dotenv import load_dotenv

from .errors import PlatformNetworkError, PlatformTimeoutError

load_dotenv()

CODEFORCES_API = os.getenv("CODEFORCES_API")


def _error_payload(platform: str, error_type: str, message: str, details=None) -> dict:
    return {
        "status": "error",
        "platform": platform,
        "error_type": error_type,
        "message": message,
        "details": details or {},
    }


def _build_fallback_id(platform: str, username: str, timestamp: str, event_type: str) -> str:
    input_str = f"{platform}_{username}_{timestamp}_{event_type}"
    return hashlib.md5(input_str.encode("utf-8")).hexdigest()


def _success_payload(platform: str, username: str, data) -> dict:
    return {
        "status": "success",
        "platform": platform,
        "username": username,
        "data": data,
    }


class CodeforcesClient:
    def __init__(self, base_url: str | None = None, timeout: tuple[int, int] = (5, 10)):
        self.base_url = base_url or CODEFORCES_API
        self.timeout = timeout

    def _get(self, url: str, params: dict | None = None) -> requests.Response:
        try:
            response = requests.get(url, params=params, timeout=self.timeout)
        except requests.Timeout as exc:
            raise PlatformTimeoutError("Codeforces request timed out") from exc
        except requests.RequestException as exc:
            raise PlatformNetworkError("Codeforces request failed") from exc

        if response.status_code >= 500:
            raise PlatformNetworkError("Codeforces server error")

        return response

    def _map_error(self, comment: str) -> dict:
        comment_lower = (comment or "").lower()
        if "not found" in comment_lower or "user with handle" in comment_lower:
            return _error_payload("codeforces", "INVALID_USERNAME", "Codeforces user not found")
        if "limit" in comment_lower or "rate" in comment_lower:
            return _error_payload("codeforces", "RATE_LIMIT", "Codeforces rate limit exceeded")
        return _error_payload("codeforces", "UNKNOWN", "Codeforces request failed")

    def get_user_info(self, username: str) -> dict:
        url = f"{self.base_url}user.info?handles={username}"
        response = self._get(url)

        if response.status_code != 200:
            return _error_payload("codeforces", "UNKNOWN", "Codeforces user fetch failed")

        response_data = response.json()
        if response_data.get("status") != "OK":
            return self._map_error(response_data.get("comment", ""))

        user = response_data.get("result", [{}])[0]
        registration_time = user.get("registrationTimeSeconds")
        created_at = None
        if registration_time:
            created_at = datetime.fromtimestamp(registration_time, tz=timezone.utc).isoformat()

        normalized = {
            "id": user.get("handle"),
            "platform": "codeforces",
            "username": user.get("handle"),
            "name": user.get("firstName"),
            "created_at": created_at,
            "rating": user.get("rating"),
            "rank": user.get("rank"),
        }
        return _success_payload("codeforces", username, normalized)

    def get_user_exists(self, username: str) -> bool:
        url = f"{self.base_url}user.info?handles={username}"
        response = self._get(url)
        if response.status_code != 200:
            return False

        response_data = response.json()
        return response_data.get("status") == "OK"

    def get_activities(self, username: str) -> list[dict] | dict:
        url = f"{self.base_url}user.status?handle={username}"
        response = self._get(url)

        if response.status_code != 200:
            return _error_payload("codeforces", "UNKNOWN", "Codeforces activities fetch failed")

        response_data = response.json()
        if response_data.get("status") != "OK":
            return self._map_error(response_data.get("comment", ""))

        normalized = []
        for event in response_data.get("result", []):
            timestamp = event.get("creationTimeSeconds")
            created_at = None
            if timestamp:
                created_at = datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat()

            event_id = event.get("id")
            if not event_id and created_at:
                event_id = _build_fallback_id("codeforces", username, created_at, "submission")

            normalized.append(
                {
                    "id": str(event_id) if event_id is not None else None,
                    "platform": "codeforces",
                    "created_at": created_at,
                    "event_type": "submission",
                    "problem_name": event.get("problem", {}).get("name"),
                    "verdict": event.get("verdict"),
                }
            )

        return _success_payload("codeforces", username, normalized)

    def get_activity_summary(self, username: str) -> list[dict] | dict:
        events_payload = self.get_activities(username)
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
            {"platform": "codeforces", "date": date, "count": count}
            for date, count in sorted(activity_map.items())
        ]
        return _success_payload("codeforces", username, summary)
