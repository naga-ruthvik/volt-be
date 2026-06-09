import asyncio
import logging

from playwright.async_api import async_playwright

from .utils import HackerRankMetricsBuilder, error_payload, success_payload

logger = logging.getLogger(__name__)


class HackerRankScraper:
    def __init__(self, headless: bool = True):
        self.headless = headless
        self.metrics_builder = HackerRankMetricsBuilder()

    async def scrape_user_dashboard(self, username: str) -> dict:
        captured_data = await self._scrape_hackerrank_stealth(username)

        badges = captured_data.get("badges")
        if not badges or "models" not in badges:
            return error_payload(
                error_type="CAPTURE_FAILED",
                message=f"Failed to capture badge data via browser network hooks for user: {username}",
            )

        dashboard_metrics = self.metrics_builder.build(badges["models"])
        return success_payload(username, data=dashboard_metrics)

    async def _scrape_hackerrank_stealth(self, username: str) -> dict:
        captured = {"badges": None, "certifications": None, "scores": None}
        data_captured_event = asyncio.Event()

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=self.headless)
            context = await browser.new_context(
                viewport={"width": 1920, "height": 1080},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (HTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
            )
            page = await context.new_page()

            async def handle_response(response):
                url = response.url.lower()
                content_type = response.headers.get("content-type", "").lower()

                if response.status == 200 and "application/json" in content_type:
                    try:
                        if "/badges" in url:
                            captured["badges"] = await response.json()
                            data_captured_event.set()
                        elif "hacker_certificate" in url:
                            captured["certifications"] = await response.json()
                        elif "scores_elo" in url:
                            captured["scores"] = await response.json()
                    except (ValueError, Exception) as e:
                        logger.warning(f"Failed to decode response JSON for {url}: {e}")

            page.on("response", handle_response)
            profile_url = f"https://www.hackerrank.com/profile/{username}"

            try:
                # Use domcontentloaded to ensure standard scripts are running before we wait for selectors
                await page.goto(profile_url, wait_until="domcontentloaded", timeout=30000)
                await page.wait_for_selector("text=My Badges", timeout=15000)

                # Scroll to ensure all lazy background calls are triggered
                await page.evaluate("window.scrollTo(0, 500)")

                try:
                    await asyncio.wait_for(data_captured_event.wait(), timeout=12.0)
                except asyncio.TimeoutError:
                    logger.warning(
                        f"Timeout hit waiting for HackerRank background APIs for {username}. Proceeding with partial data."
                    )

            except Exception as e:
                logger.error(f"Error executing browser routine for {username}: {e}")
            finally:
                await context.close()
                await browser.close()

            return captured
