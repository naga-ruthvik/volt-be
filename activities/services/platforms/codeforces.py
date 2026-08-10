"""Codeforces client with normalized outputs and standardized error payloads.

Public methods
--------------
``get_user_info(username)``
    Profile metadata for a single user.

``get_user_exists(username)``
    ``True`` if the handle resolves to a Codeforces account.

``get_activity_data(username)``
    **Primary sync method.** Makes one ``user.status`` request and returns
    both the activity heatmap and solved-problem statistics derived from it.

``get_activities(username)``
    Raw per-submission event list. Prefer ``get_activity_data()`` during sync
    flows; use this only when the full event list is explicitly needed.

``get_activity_summary(username)``
    Date → count heatmap only. Prefer ``get_activity_data()`` during sync
    flows; use this only when the heatmap alone is explicitly needed.

``get_contest_history(username)``
    Rating-change history per contest.

Payload shapes
--------------
Success (``get_activity_data``)::

    {
        "status": "success",
        "platform": "codeforces",
        "username": str,
        "data": {
            "activity_summary": [
                {"platform": "codeforces", "date": "YYYY-MM-DD", "count": int},
                ...
            ],
            "stats": {
                "total_solved_problems": int,
                "rating_distribution": {rating: count, ...},
                "topic_distribution": {tag: count, ...},
                "solved_languages": {lang: count, ...},
            },
        },
    }

Grouped summaries (``get_activity_summary``)::

    {
        "status": "success",
        "platform": "codeforces",
        "username": str,
        "data": [{"date": "YYYY-MM-DD", "count": int, "platform": "codeforces"}],
    }

Item lists (``get_activities``)::

    {
        "status": "success",
        "platform": "codeforces",
        "username": str,
        "data": [
            {
                "id": str,
                "platform": "codeforces",
                "created_at": str,
                "event_type": "submission",
                "problem_name": str,
                "verdict": str,
            }
        ],
    }
"""

import hashlib
import os
from collections import defaultdict
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


def _build_fallback_id(
    platform: str, username: str, timestamp: str, event_type: str
) -> str:
    input_str = f"{platform}_{username}_{timestamp}_{event_type}"
    return hashlib.md5(input_str.encode("utf-8")).hexdigest()  # noqa: S324


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
            return _error_payload(
                "codeforces", "INVALID_USERNAME", "Codeforces user not found"
            )
        if "limit" in comment_lower or "rate" in comment_lower:
            return _error_payload(
                "codeforces", "RATE_LIMIT", "Codeforces rate limit exceeded"
            )
        return _error_payload("codeforces", "UNKNOWN", "Codeforces request failed")

    # Private helpers
    def _fetch_submissions(self, username: str) -> dict:
        """Fetch raw submission data from the Codeforces API.

        Returns the raw parsed JSON dict (not a normalized payload).
        On a non-200 response, returns a synthetic ``{"status": "FAILED"}``
        so all callers can use a uniform ``raw.get("status") != "OK"`` check.
        """
        url = f"{self.base_url}user.status?handle={username}"
        response = self._get(url)
        if response.status_code != 200:
            return {"status": "FAILED", "comment": "fetch_failed"}
        return response.json()

    def _build_activity_summary(self, submissions: list[dict]) -> list[dict]:
        """Derive a sorted date → count heatmap from a raw submissions list."""
        activity_map: dict[str, int] = {}
        for sub in submissions:
            timestamp = sub.get("creationTimeSeconds")
            if not timestamp:
                continue
            date = datetime.fromtimestamp(timestamp, tz=timezone.utc).date().isoformat()
            activity_map[date] = activity_map.get(date, 0) + 1

        return [
            {"platform": "codeforces", "date": date, "count": count}
            for date, count in sorted(activity_map.items())
        ]

    def _build_stats(self, submissions: list[dict]) -> dict:
        """Derive solved-problem statistics from a raw submissions list."""
        solved_problems: set[str] = set()
        rating_counts: defaultdict[str | int, int] = defaultdict(int)
        topic_counts: defaultdict[str, int] = defaultdict(int)
        solved_language_counts: defaultdict[str, int] = defaultdict(int)

        for sub in submissions:
            lang = sub.get("programmingLanguage", "Unknown")
            verdict = sub.get("verdict")
            problem = sub.get("problem", {})

            contest_id = problem.get("contestId")
            index = problem.get("index")
            problem_id = f"{contest_id}-{index}"

            if verdict == "OK" and problem_id not in solved_problems:
                solved_problems.add(problem_id)
                solved_language_counts[lang] += 1
                rating = problem.get("rating", "Unrated")
                rating_counts[rating] += 1
                for tag in problem.get("tags", []):
                    topic_counts[tag] += 1

        return {
            "total_solved_problems": len(solved_problems),
            "rating_distribution": dict(rating_counts),
            "topic_distribution": dict(topic_counts),
            "solved_languages": dict(solved_language_counts),
        }

    # Public Methods
    def get_user_info(self, username: str) -> dict:
        url = f"{self.base_url}user.info?handles={username}"
        response = self._get(url)

        if response.status_code != 200:
            return _error_payload(
                "codeforces", "UNKNOWN", "Codeforces user fetch failed"
            )

        response_data = response.json()
        if response_data.get("status") != "OK":
            return self._map_error(response_data.get("comment", ""))

        user = response_data.get("result", [{}])[0]
        registration_time = user.get("registrationTimeSeconds")
        created_at = None
        if registration_time:
            created_at = datetime.fromtimestamp(
                registration_time, tz=timezone.utc
            ).isoformat()

        normalized = {
            "id": user.get("handle"),
            "platform": "codeforces",
            "username": user.get("handle"),
            "name": user.get("firstName"),
            "created_at": created_at,
            "rating": user.get("rating"),
            "rank": user.get("rank"),
            "max_rating": user.get("maxRating"),
            "max_rank": user.get("maxRank"),
        }
        return _success_payload("codeforces", username, normalized)

    def get_user_exists(self, username: str) -> bool:
        url = f"{self.base_url}user.info?handles={username}"
        response = self._get(url)
        if response.status_code != 200:
            return False

        response_data = response.json()
        return response_data.get("status") == "OK"

    def get_activity_data(self, username: str) -> dict:
        """Fetch all submission-derived data in a single API call.

        Makes one HTTP request to ``user.status`` and derives both the
        activity heatmap and solved-problem statistics from the same response.

        Returns a success payload whose ``data`` key contains::

            {
                "activity_summary": [
                    {"platform": "codeforces", "date": "YYYY-MM-DD", "count": int},
                    ...
                ],
                "stats": {
                    "total_solved_problems": int,
                    "rating_distribution": {rating: count, ...},
                    "topic_distribution": {tag: count, ...},
                    "solved_languages": {lang: count, ...},
                },
            }

        On failure, returns a standard error payload.
        """
        raw = self._fetch_submissions(username)
        if raw.get("status") != "OK":
            return self._map_error(raw.get("comment", ""))

        submissions = raw.get("result", [])
        return _success_payload(
            "codeforces",
            username,
            {
                "activity_summary": self._build_activity_summary(submissions),
                "stats": self._build_stats(submissions),
            },
        )

    def get_activities(self, username: str) -> dict:
        """Return the raw per-submission event list for a user.

        Prefer ``get_activity_data()`` during sync flows; use this method only
        when the full event list is explicitly needed (e.g. debugging).
        """
        raw = self._fetch_submissions(username)
        if raw.get("status") != "OK":
            return self._map_error(raw.get("comment", ""))

        normalized = []
        for event in raw.get("result", []):
            timestamp = event.get("creationTimeSeconds")
            created_at = None
            if timestamp:
                created_at = datetime.fromtimestamp(
                    timestamp, tz=timezone.utc
                ).isoformat()

            event_id = event.get("id")
            if not event_id and created_at:
                event_id = _build_fallback_id(
                    "codeforces", username, created_at, "submission"
                )

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

    def get_activity_summary(self, username: str) -> dict:
        """Return only the date → count heatmap for a user.

        Prefer ``get_activity_data()`` during sync flows; use this method only
        when the heatmap alone is explicitly needed (e.g. debugging).
        """
        raw = self._fetch_submissions(username)
        if raw.get("status") != "OK":
            return self._map_error(raw.get("comment", ""))

        submissions = raw.get("result", [])
        return _success_payload(
            "codeforces",
            username,
            self._build_activity_summary(submissions),
        )

    def get_contest_history(self, username: str) -> dict:
        # TODO: Wire contest history into the sync flow and fix the bare
        url = f"{self.base_url}/user.rating?handle={username}"
        response = self._get(url)
        if response.status_code != 200:
            return _error_payload(
                "codeforces", "UNKNOWN", "Codeforces contest history fetch failed"
            )
        response_data = response.json()
        if response_data.get("status") != "OK":
            return self._map_error(response_data.get("comment", ""))
        results = response_data.get("result", [])
        for result in results:
            # TODO: confirm if the contest start date is equal to the rating updated date
            result.pop("handle", None)
            result["contest_id"] = result.get("contestId")
            result["contest_name"] = result.get("contestName")
            result["old_rating"] = result.get("oldRating")
            result["new_rating"] = result.get("newRating")
            rating_updated_time = (
                datetime.fromtimestamp(result.get("ratingUpdatedTime"), tz=timezone.utc)
                .date()
                .isoformat()
            )
            result["rating_updated_time"] = rating_updated_time
            result.pop("contestId", None)
            result.pop("contestName", None)
            result.pop("ratingUpdatedTime", None)
            result.pop("oldRating", None)
            result.pop("newRating", None)
        return _success_payload("codeforces", username, results)
