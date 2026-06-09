import requests

from ..errors import PlatformNetworkError, PlatformTimeoutError
from .utils import HackerRankMetricsBuilder, error_payload, success_payload

HACKER_RANK_API = "https://www.hackerrank.com/rest/hackers/"
HACKER_RANK_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (HTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
}


class HackerRankClient:
    def __init__(self, base_url: str | None = None, timeout: tuple[int, int] = (5, 10)):
        self.base_url = base_url or HACKER_RANK_API
        self.timeout = timeout
        self.metrics_builder = HackerRankMetricsBuilder()

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
            return (
                response.status_code == 403
                and "rate limit" in payload.get("message", "").lower()
            )
        except ValueError:
            return False

    def get_user_info(self, username: str) -> dict:
        url = f"{self.base_url}{username}"
        response = self._get(url)
        if response.status_code == 404:
            return error_payload("INVALID_USERNAME", f"User '{username}' not found.")
        elif self._is_rate_limited(response):
            return error_payload(
                "RateLimitExceeded", "HackerRank API rate limit exceeded."
            )
        elif response.status_code != 200:
            return error_payload("UNKNOWN", "Unable to fetch data from Hacker Rank")

        data = response.json().get("model")
        if not data:
            return error_payload("DATA_MISSING", "User profile data was empty.")

        user_id = data.get("id")
        normalized = {
            "id": str(user_id) if user_id is not None else None,
            "username": data.get("username"),
            "country": data.get("country"),
            "created_at": data.get("created_at"),
            "name": data.get("name"),
            "first_name": data.get("personal_first_name"),
            "last_name": data.get("personal_last_name"),
        }
        return success_payload(username, data=normalized)

    def get_user_metrics(self, username: str) -> dict:
        url = f"{self.base_url}{username}/badges"
        response = self._get(url)
        if response.status_code != 200:
            return error_payload("UNKNOWN", "Unable to fetch metrics.")

        data = response.json().get("models", [])
        dashboard_metrics = self.metrics_builder.build(data)
        return success_payload(username, data=dashboard_metrics)
