"""Platform API Health Check — checks every upstream endpoint this project depends on.

Run from the project root:

    uv run python activities/services/platforms/tests/health_check.py

Probes each platform's cheapest identifiable endpoint and reports reachability,
HTTP status, and latency in a formatted table.

Exit codes
----------
0  All probes passed.
1  One or more probes failed.

No Django setup required — platform clients are pure HTTP.
"""

import os
import sys
import time
from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# Make the project root importable when run directly.
# ---------------------------------------------------------------------------
_PROJECT_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "..")
)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import asyncio  # noqa: E402

import aiohttp  # noqa: E402
import requests  # noqa: E402

from activities.services.platforms.codeforces import CodeforcesClient  # noqa: E402
from activities.services.platforms.errors import (  # noqa: E402
    PlatformNetworkError,
    PlatformTimeoutError,
)
from activities.services.platforms.github import GitHubClient  # noqa: E402
from activities.services.platforms.hackerrank import HackerRankClient  # noqa: E402
from activities.services.platforms.leetcode import LeetcodeClient  # noqa: E402

# ---------------------------------------------------------------------------
# Fixed probe handles — known-good public accounts on each platform.
# ---------------------------------------------------------------------------
GITHUB_HANDLE = "torvalds"
CODEFORCES_HANDLE = "tourist"
LEETCODE_HANDLE = "neal_wu"  # Active competitive programmer with contest history
HACKERRANK_HANDLE = "kondenagaruthvik"
CODECHEF_HANDLE = "gennady.korotkevich"
GFG_HANDLE = "naga_ruthvik"


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------


@dataclass
class HealthResult:
    platform: str
    probe: str
    ok: bool
    latency_ms: int
    detail: str = ""
    extra: dict = field(default_factory=dict)  # raw response keys for debugging


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _timed(fn):
    """Run fn(), return (result, elapsed_ms)."""
    t0 = time.perf_counter()
    result = fn()
    elapsed = int((time.perf_counter() - t0) * 1000)
    return result, elapsed


def _is_error(payload: dict) -> bool:
    return isinstance(payload, dict) and payload.get("status") == "error"


def _safe_probe(platform: str, probe: str, fn) -> HealthResult:
    """
    Call fn() and convert any exception into a failed HealthResult.
    Catches PlatformTimeoutError, PlatformNetworkError, and everything else.
    """
    t0 = time.perf_counter()
    try:
        result = fn()
        elapsed = int((time.perf_counter() - t0) * 1000)
        return (
            result
            if isinstance(result, HealthResult)
            else HealthResult(
                platform=platform,
                probe=probe,
                ok=False,
                latency_ms=elapsed,
                detail="probe returned unexpected type",
            )
        )
    except PlatformTimeoutError:
        elapsed = int((time.perf_counter() - t0) * 1000)
        return HealthResult(
            platform=platform,
            probe=probe,
            ok=False,
            latency_ms=elapsed,
            detail="TIMEOUT",
        )
    except PlatformNetworkError as exc:
        elapsed = int((time.perf_counter() - t0) * 1000)
        return HealthResult(
            platform=platform,
            probe=probe,
            ok=False,
            latency_ms=elapsed,
            detail=f"NETWORK_ERROR: {exc}",
        )
    except Exception as exc:  # noqa: BLE001
        elapsed = int((time.perf_counter() - t0) * 1000)
        return HealthResult(
            platform=platform,
            probe=probe,
            ok=False,
            latency_ms=elapsed,
            detail=f"EXCEPTION: {type(exc).__name__}: {exc}",
        )


# ---------------------------------------------------------------------------
# Individual probes
# ---------------------------------------------------------------------------


def _probe_github() -> HealthResult:
    def run():
        t0 = time.perf_counter()
        client = GitHubClient(base_url="https://api.github.com")
        payload = client.get_user_info(GITHUB_HANDLE)
        elapsed = int((time.perf_counter() - t0) * 1000)

        if _is_error(payload):
            return HealthResult(
                platform="GitHub",
                probe=f"GET /users/{GITHUB_HANDLE}",
                ok=False,
                latency_ms=elapsed,
                detail=f"{payload.get('error_type')}: {payload.get('message')}",
            )
        data = payload.get("data", {})
        ok = bool(data.get("username"))
        return HealthResult(
            platform="GitHub",
            probe=f"GET /users/{GITHUB_HANDLE}",
            ok=ok,
            latency_ms=elapsed,
            detail="" if ok else "username field missing in response",
        )

    return _safe_probe("GitHub", f"GET /users/{GITHUB_HANDLE}", run)


def _probe_codeforces() -> HealthResult:
    def run():
        t0 = time.perf_counter()
        client = CodeforcesClient(base_url="https://codeforces.com/api/")
        payload = client.get_user_info(CODEFORCES_HANDLE)
        elapsed = int((time.perf_counter() - t0) * 1000)

        if _is_error(payload):
            return HealthResult(
                platform="Codeforces",
                probe=f"user.info?handles={CODEFORCES_HANDLE}",
                ok=False,
                latency_ms=elapsed,
                detail=f"{payload.get('error_type')}: {payload.get('message')}",
            )
        ok = bool(payload.get("data", {}).get("username"))
        return HealthResult(
            platform="Codeforces",
            probe=f"user.info?handles={CODEFORCES_HANDLE}",
            ok=ok,
            latency_ms=elapsed,
            detail="" if ok else "username field missing",
        )

    return _safe_probe("Codeforces", f"user.info?handles={CODEFORCES_HANDLE}", run)


def _probe_leetcode_profile() -> HealthResult:
    probe_label = f"GraphQL getUserProfile({LEETCODE_HANDLE!r})"

    def run():
        t0 = time.perf_counter()
        client = LeetcodeClient()
        payload = client.get_user_profile(LEETCODE_HANDLE)
        elapsed = int((time.perf_counter() - t0) * 1000)

        if _is_error(payload):
            return HealthResult(
                platform="LeetCode",
                probe=probe_label,
                ok=False,
                latency_ms=elapsed,
                detail=f"{payload.get('error_type')}: {payload.get('message')}",
            )
        ok = bool(payload.get("data", {}).get("username"))
        return HealthResult(
            platform="LeetCode",
            probe=probe_label,
            ok=ok,
            latency_ms=elapsed,
            detail="" if ok else "matchedUser missing in response",
        )

    return _safe_probe("LeetCode", probe_label, run)


def _probe_leetcode_contest_ranking() -> HealthResult:
    """
    This is the probe that corresponds to the warning you saw:
      'Failed to fetch LeetCode contest ranking for naga_ruthvik; skipping.'

    It tells us definitively:
      - HTTP 400 / errors key  → GraphQL schema changed or query is invalid.
      - HTTP 200 + null result → API is fine; that user just has no contest history.
      - HTTP 200 + data        → fully working.
    """
    probe_label = f"GraphQL contestRankingInfo({LEETCODE_HANDLE!r})"

    def run():
        t0 = time.perf_counter()
        client = LeetcodeClient()
        payload = client.get_user_contest_ranking_info(LEETCODE_HANDLE)
        elapsed = int((time.perf_counter() - t0) * 1000)

        if _is_error(payload):
            return HealthResult(
                platform="LeetCode (contest)",
                probe=probe_label,
                ok=False,
                latency_ms=elapsed,
                detail=f"{payload.get('error_type')}: {payload.get('message')}",
            )

        # A null ranking is fine — the user may not have participated.
        # We only care that the endpoint responded without errors.
        data = payload.get("data", {})
        ok = "ranking" in data  # key present = endpoint worked
        return HealthResult(
            platform="LeetCode (contest)",
            probe=probe_label,
            ok=ok,
            latency_ms=elapsed,
            detail="" if ok else f"unexpected response shape: {list(data.keys())}",
            extra={"ranking_null": data.get("ranking") is None},
        )

    return _safe_probe("LeetCode (contest)", probe_label, run)


def _probe_hackerrank() -> HealthResult:
    probe_label = f"GET /hackers/{HACKERRANK_HANDLE}"

    def run():
        t0 = time.perf_counter()
        client = HackerRankClient()
        payload = client.get_user_info(HACKERRANK_HANDLE)
        elapsed = int((time.perf_counter() - t0) * 1000)

        if _is_error(payload):
            return HealthResult(
                platform="HackerRank",
                probe=probe_label,
                ok=False,
                latency_ms=elapsed,
                detail=f"{payload.get('error_type')}: {payload.get('message')}",
            )
        ok = bool(payload.get("data", {}).get("username"))
        return HealthResult(
            platform="HackerRank",
            probe=probe_label,
            ok=ok,
            latency_ms=elapsed,
            detail="" if ok else "username field missing",
        )

    return _safe_probe("HackerRank", probe_label, run)


def _probe_codechef() -> HealthResult:
    """
    Lightweight aiohttp GET — checks the page loads without error.
    Full Playwright scrape is not used here to keep the health check fast.
    """
    url = f"https://www.codechef.com/users/{CODECHEF_HANDLE}"
    probe_label = f"GET /users/{CODECHEF_HANDLE}"

    async def _fetch():
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/121.0.0.0 Safari/537.36"
            )
        }
        timeout = aiohttp.ClientTimeout(total=15)
        async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
            async with session.get(url) as resp:
                return resp.status, await resp.text()

    def run():
        t0 = time.perf_counter()
        try:
            status, body = asyncio.run(_fetch())
        except asyncio.TimeoutError:
            elapsed = int((time.perf_counter() - t0) * 1000)
            return HealthResult(
                platform="CodeChef",
                probe=probe_label,
                ok=False,
                latency_ms=elapsed,
                detail="TIMEOUT",
            )
        except Exception as exc:  # noqa: BLE001
            elapsed = int((time.perf_counter() - t0) * 1000)
            return HealthResult(
                platform="CodeChef",
                probe=probe_label,
                ok=False,
                latency_ms=elapsed,
                detail=f"NETWORK_ERROR: {exc}",
            )

        elapsed = int((time.perf_counter() - t0) * 1000)
        if status != 200:
            return HealthResult(
                platform="CodeChef",
                probe=probe_label,
                ok=False,
                latency_ms=elapsed,
                detail=f"HTTP {status}",
            )

        # Basic sanity: ensure it's not a 404/error page served with 200
        page_ok = "rating-number" in body or "user-country-name" in body
        return HealthResult(
            platform="CodeChef",
            probe=probe_label,
            ok=page_ok,
            latency_ms=elapsed,
            detail=""
            if page_ok
            else "page loaded but expected profile elements not found",
        )

    return _safe_probe("CodeChef", probe_label, run)


def _probe_geeksforgeeks() -> HealthResult:
    """
    Lightweight aiohttp GET — checks the profile page loads without error.
    Full Playwright scrape is not used here to keep the health check fast.
    """
    url = f"https://www.geeksforgeeks.org/user/{GFG_HANDLE}/"
    probe_label = f"GET /user/{GFG_HANDLE}/"

    async def _fetch():
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/121.0.0.0 Safari/537.36"
            )
        }
        timeout = aiohttp.ClientTimeout(total=15)
        async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
            async with session.get(url) as resp:
                return resp.status, await resp.text()

    def run():
        t0 = time.perf_counter()
        try:
            status, body = asyncio.run(_fetch())
        except asyncio.TimeoutError:
            elapsed = int((time.perf_counter() - t0) * 1000)
            return HealthResult(
                platform="GeeksForGeeks",
                probe=probe_label,
                ok=False,
                latency_ms=elapsed,
                detail="TIMEOUT",
            )
        except Exception as exc:  # noqa: BLE001
            elapsed = int((time.perf_counter() - t0) * 1000)
            return HealthResult(
                platform="GeeksForGeeks",
                probe=probe_label,
                ok=False,
                latency_ms=elapsed,
                detail=f"NETWORK_ERROR: {exc}",
            )

        elapsed = int((time.perf_counter() - t0) * 1000)
        if status != 200:
            return HealthResult(
                platform="GeeksForGeeks",
                probe=probe_label,
                ok=False,
                latency_ms=elapsed,
                detail=f"HTTP {status}",
            )

        page_ok = (
            "profilePicSection" in body or "score_card" in body or "gfg-streak" in body
        )
        return HealthResult(
            platform="GeeksForGeeks",
            probe=probe_label,
            ok=page_ok,
            latency_ms=elapsed,
            detail=""
            if page_ok
            else "page loaded but expected profile elements not found",
        )

    return _safe_probe("GeeksForGeeks", probe_label, run)


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

_PROBES = [
    _probe_github,
    _probe_codeforces,
    _probe_leetcode_profile,
    _probe_leetcode_contest_ranking,
    _probe_hackerrank,
    _probe_codechef,
    _probe_geeksforgeeks,
]


def run_all_probes() -> list[HealthResult]:
    results = []
    for probe_fn in _PROBES:
        print(
            f"  Probing {probe_fn.__name__.replace('_probe_', '').replace('_', ' ').title()}...",
            end=" ",
            flush=True,
        )
        result = probe_fn()
        print("OK" if result.ok else "FAIL")
        results.append(result)
    return results


# ---------------------------------------------------------------------------
# Report printer
# ---------------------------------------------------------------------------

_COL_PLATFORM = 24
_COL_STATUS = 9
_COL_LATENCY = 9


def _row(platform: str, status: str, latency: str, detail: str = "") -> str:
    p = platform.ljust(_COL_PLATFORM)
    s = status.ljust(_COL_STATUS)
    l_ = latency.ljust(_COL_LATENCY)
    return f"  {p}  {s}  {l_}  {detail}".rstrip()


def print_report(results: list[HealthResult]) -> None:
    from datetime import datetime, timezone

    now = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    divider = "=" * 70
    header = _row("Platform", "Status", "Latency", "Detail")

    print(f"\nPlatform Health Check — {now}")
    print(divider)
    print(header)
    print("-" * 70)

    for r in results:
        status = "OK" if r.ok else "FAIL"
        latency = f"{r.latency_ms}ms"
        detail = r.detail

        # Extra info for contest ranking — clarify null vs broken
        if r.platform == "LeetCode (contest)" and r.ok:
            if r.extra.get("ranking_null"):
                detail = "endpoint OK — probe handle has no contest history"

        print(_row(r.platform, status, latency, detail))

    passing = sum(1 for r in results if r.ok)
    total = len(results)
    failing = total - passing

    print(divider)
    summary = f"  {passing}/{total} healthy"
    if failing:
        summary += f"  ({failing} failing)"
    print(summary)
    print()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("\nRunning platform health probes...")
    results = run_all_probes()
    print_report(results)

    any_failed = any(not r.ok for r in results)
    sys.exit(1 if any_failed else 0)
