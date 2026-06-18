# codechef/scraper.py
import asyncio
import json
import logging
import re

import aiohttp
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


def success_payload(username, data):
    return {"status": "success", "username": username, "data": data}


def error_payload(error_type, message):
    return {"status": "error", "error_type": error_type, "message": message}


class CodeChefScraper:
    def __init__(self, timeout: int = 15):
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        }

    async def scrape_user_profile(self, username: str) -> dict:
        """
        Main public method to fetch and parse the CodeChef profile.
        """
        html_content = await self._fetch_html_async(username)

        if not html_content:
            return error_payload(
                error_type="FETCH_FAILED",
                message=f"Failed to fetch HTML or user not found for CodeChef user: {username}",
            )

        try:
            # TODO: consider wrapping this in asyncio.to_thread()
            dashboard_metrics = self._parse_html(html_content, username)
            return success_payload(username, data=dashboard_metrics)

        except Exception as e:
            return error_payload(
                error_type="PARSE_FAILED",
                message=f"Failed to parse profile structure for user: {username}. DOM might have changed.",
            )

    async def _fetch_html_async(self, username: str) -> str:
        """
        Asynchronously fetches the raw HTML from CodeChef.
        """
        url = f"https://www.codechef.com/users/{username}"

        try:
            async with aiohttp.ClientSession(
                timeout=self.timeout, headers=self.headers
            ) as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        return await response.text()
                    else:
                        logger.warning(f"CodeChef returned status {response.status} for user {username}")
                        return None
        except asyncio.TimeoutError:
            logger.warning(f"CodeChef request timed out for user {username}")
            return None
        except aiohttp.ClientError as e:
            logger.error(f"CodeChef network error for {username}: {e}")
            return None

    def _parse_html(self, html_content: str, username: str) -> dict:
        """
        Synchronous method to extract data from the DOM and JS variables.
        """
        soup = BeautifulSoup(html_content, "html.parser")

        # --- 1. Extract Heatmap Data (Regex) ---
        heatmap_data = []
        heatmap_match = re.search(
            r"var userDailySubmissionsStats = (\[.*?\]);", html_content
        )
        if heatmap_match:
            try:
                raw_heatmap = json.loads(heatmap_match.group(1))
                # Normalize dates to YYYY-MM-DD
                for item in raw_heatmap:
                    y, m, d = item["date"].split("-")
                    padded_date = f"{y}-{int(m):02d}-{int(d):02d}"
                    heatmap_data.append({"date": padded_date, "value": item["value"]})
            except (ValueError, KeyError, json.JSONDecodeError) as e:
                logger.warning(f"Failed to parse heatmap for {username}: {e}")

        # --- 2. Extract Rating History (Regex) ---
        rating_history = []
        rating_match = re.search(r"var all_rating = (\[.*?\]);", html_content)
        if rating_match:
            try:
                rating_history = json.loads(rating_match.group(1))
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse rating history for {username}: {e}")

        # --- 3. Extract DOM Elements ---
        name_elem = soup.find("h1", class_="h2-style")
        name = name_elem.text.strip() if name_elem else "N/A"

        country_elem = soup.find("span", class_="user-country-name")
        country = country_elem.text.strip() if country_elem else "N/A"

        current_rating = 0
        rating_elem = soup.find("div", class_="rating-number")
        if rating_elem:
            match = re.search(r"\d+", rating_elem.text)
            if match:
                current_rating = int(match.group())

        stars_elem = soup.find("span", class_="rating")
        stars = stars_elem.text.strip() if stars_elem else "Unrated"

        rank_elems = soup.select(".rating-ranks ul li a strong")
        global_rank = rank_elems[0].text.strip() if len(rank_elems) > 0 else "Inactive"
        country_rank = rank_elems[1].text.strip() if len(rank_elems) > 1 else "Inactive"

        total_solved = 0
        solved_elem = soup.find("h3", string=re.compile(r"Total Problems Solved:"))
        if solved_elem:
            solved_match = re.search(r"\d+", solved_elem.text)
            if solved_match:
                total_solved = int(solved_match.group())

        return {
            "profile": {
                "name": name,
                "username": username,
                "country": country,
                "currentRating": current_rating,
                "stars": stars,
                "globalRank": global_rank,
                "countryRank": country_rank,
                "totalSolved": total_solved,
                "ratingHistory": rating_history,
            },
            "heatmap": heatmap_data,
        }
