import requests

from .errors import PlatformNetworkError, PlatformTimeoutError

HACKER_RANK_API = "https://www.hackerrank.com/rest/hackers/"
HACKER_RANK_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (HTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}


def _error_payload(error_type: str, message: str, details=None) -> dict:
    return {
        "status": "error",
        "platform": "HACKER RANK",
        "error_type": error_type,
        "message": message,
        "details": details or {},
    }


def _success_payload(username: str, data) -> dict:
    return {
        "status": "success",
        "platform": "HACKER RANK",
        "username": username,
        "data": data,
    }


class HackerRankClient:
    def __init__(self, base_url: str | None = None, timeout: tuple[int, int] = (5, 10)):
        self.base_url = base_url or HACKER_RANK_API
        self.timeout = timeout

    # private methods
    def _get(self, url: str, params: dict | None = None) -> requests.Response:
        try:
            response = requests.get(
                url, params=params, timeout=self.timeout, headers=HACKER_RANK_HEADERS
            )
        except requests.Timeout as exc:
            raise PlatformTimeoutError("HackerRank request timed out") from exc
        except requests.RequestException as exc:
            raise PlatformNetworkError("HackerRank request failed") from exc

        if response.status_code >= 500:
            raise PlatformNetworkError("HackerRank server error")

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

    def _get_total_questions_solved(self, badges_data: list[dict]) -> int:
        total = 0
        for badge in badges_data:
            total += badge.get("solved", 0)
        return total

    def _get_questions_by_badge(self, badges_data: list[dict]) -> dict:
        # TODO: iterate over badges to get the data
        pass

    # public methods
    def get_user_info(self, username: str) -> dict:
        url = f"{HACKER_RANK_API}{username}"
        response = self._get(url)
        if response.status_code == 404:
            return _error_payload(
                error_type="INVALID_USERNAME",
                message=f"User '{username}' not found on HackerRank.",
            )
        elif self._is_rate_limited(response):
            return _error_payload(
                error_type="RateLimitExceeded",
                message="HackerRank API rate limit exceeded.",
            )
        elif response.status_code != 200:
            return _error_payload(
                error_type="UNKNOWN",
                message="Unable to fetch data from Hacker Rank",
            )
        response_data = response.json()
        data = response_data.get("model")
        normalized = {
            "id": str(data.get("id")),
            "username": data.get("username"),
            "country": data.get("country"),
            "created_at": data.get("created_at"),
            "name": data.get("name"),
            "first_name": data.get("personal_first_name"),
            "last_name": data.get("personal_last_name"),
        }
        return _success_payload(username, data=normalized)

    def get_user_exists(self, username: str) -> bool:
        url = f"{HACKER_RANK_API}{username}"
        try:
            response = self._get(url)
            return response.status_code == 200
        except (PlatformTimeoutError, PlatformNetworkError):
            return False

    def get_user_activities(self, username: str) -> dict:
        url = f"{HACKER_RANK_API}{username}/badges"
        response = self._get(url)
        if response.status_code == 404:
            return _error_payload(
                error_type="INVALID_USERNAME",
                message=f"User '{username}' not found on HackerRank.",
            )
        elif self._is_rate_limited(response):
            return _error_payload(
                error_type="RateLimitExceeded",
                message="HackerRank API rate limit exceeded.",
            )
        elif response.status_code != 200:
            return _error_payload(
                error_type="UNKNOWN",
                message="Unable to fetch data from Hacker Rank",
            )
        response_data = response.json()
        data = response_data.get("models")
        total_questions_solved: int = self._get_total_questions_solved(data)
        # questions, points, name of each badge
        # badges_details: dict = self._get_questions_by_badge(data)

        normalized_data = {
            "total_questions_solved": total_questions_solved,
            # "badges": badges_details,
        }
        return _success_payload(username, data=normalized_data)
