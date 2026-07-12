import logging

from playwright.async_api import async_playwright

logger = logging.getLogger(__name__)


def success_payload(username: str, data: dict) -> dict:
    return {
        "status": "success",
        "platform": "geeksforgeeks",
        "username": username,
        "data": data,
    }


def error_payload(error_type: str, message: str, details: dict | None = None) -> dict:
    return {
        "status": "error",
        "platform": "geeksforgeeks",
        "error_type": error_type,
        "message": message,
        "details": details or {},
    }


class GeeksForGeeksScraper:
    def __init__(self, headless: bool = True):
        self.headless = headless

    async def scrape_user_profile(self, username: str) -> dict:
        captured_data = await self._scrape_gfg_profile(username)

        if not captured_data:
            return error_payload(
                error_type="CAPTURE_FAILED",
                message=(
                    f"Failed to capture GeeksforGeeks profile data for user: {username}"
                ),
                details={"username": username},
            )

        return success_payload(username=username, data=captured_data)

    async def _scrape_gfg_profile(self, username: str) -> dict | None:
        url = f"https://www.geeksforgeeks.org/profile/{username}?tab=activity"

        async with async_playwright() as p:
            browser = None
            context = None
            try:
                browser = await p.chromium.launch(headless=self.headless)
                context = await browser.new_context(
                    viewport={"width": 1920, "height": 1080},
                    user_agent=(
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/120.0.0.0 Safari/537.36"
                    ),
                )
                page = await context.new_page()

                await page.goto(url, wait_until="networkidle", timeout=30000)

                try:
                    await page.wait_for_selector(
                        '[class*="NewProfile_name"]', timeout=15000
                    )
                except Exception:
                    logger.warning(
                        "Timeout waiting for GFG profile to load: %s", username
                    )
                    return None

                name_locator = page.locator('[class*="NewProfile_name"]').first
                name = (
                    (await name_locator.inner_text()).split("\n")[0].strip()
                    if await name_locator.count()
                    else "N/A"
                )

                institute_locator = page.locator(
                    '[class*="NewProfile_designation"]'
                ).first
                institute = (
                    await institute_locator.inner_text()
                    if await institute_locator.count()
                    else "N/A"
                )

                scores: dict[str, str] = {}
                score_rows = await page.locator(
                    '[class*="ScoreContainer_score-row"]'
                ).all()
                for row in score_rows:
                    label_locator = row.locator('[class*="ScoreContainer_label"]').first
                    value_locator = row.locator('[class*="ScoreContainer_value"]').first
                    if await label_locator.count() and await value_locator.count():
                        label = (await label_locator.inner_text()).strip()
                        value = (await value_locator.inner_text()).strip()
                        scores[label] = value

                difficulty_stats: dict[str, int | str | None] = {}
                difficulty_items = await page.locator(
                    '[class*="DoughnutChart_legendItem"]'
                ).all()
                for item in difficulty_items:
                    raw = (await item.inner_text()).strip()  # e.g. "Easy (94)"
                    if not raw:
                        continue
                    if "(" in raw and raw.endswith(")"):
                        label, _, rest = raw.partition(" (")
                        count = rest.rstrip(")")
                        difficulty_stats[label.strip()] = (
                            int(count) if count.isdigit() else count
                        )
                    else:
                        difficulty_stats[raw] = None

                potd_stats: dict[str, str] = {}
                potd_items = await page.locator(
                    '[class*="PotdContainer_statItem"]'
                ).all()
                for item in potd_items:
                    label_locator = item.locator(
                        '[class*="PotdContainer_statLabel"]'
                    ).first
                    value_locator = item.locator(
                        '[class*="PotdContainer_statValue"]'
                    ).first
                    if await label_locator.count() and await value_locator.count():
                        label = (
                            (await label_locator.inner_text()).replace(":", "").strip()
                        )
                        value = (await value_locator.inner_text()).strip()
                        potd_stats[label] = value

                heatmap_exists = await page.locator(".ch-domain").count() > 0

                personal_info = {
                    "userName": username,
                    "fullName": name,
                    "institute": institute,
                }
                problem_stats = {
                    "codingScore": scores.get("Coding Score", "0"),
                    "totalProblemsSolved": scores.get("Problems Solved", "0"),
                    "instituteRank": scores.get("Institute Rank", "0"),
                    "currentStreak": potd_stats.get("Current Streak", "0"),
                    "maxStreak": potd_stats.get("Longest Streak", "0"),
                    "difficultyStats": difficulty_stats,
                }

                return {
                    "personalInfo": personal_info,
                    "problemStats": problem_stats,
                    "heatmapAvailable": heatmap_exists,
                }

            except TimeoutError as e:
                logger.warning("GFG scrape timed out for %s: %s", username, e)
                return None
            except Exception as e:
                logger.exception("GFG scrape failed for %s: %s", username, e)
                return None
            finally:
                if context is not None:
                    await context.close()
                if browser is not None:
                    await browser.close()


__all__ = ["GeeksForGeeksScraper"]
