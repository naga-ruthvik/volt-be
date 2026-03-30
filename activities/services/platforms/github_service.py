import os

import requests
from dotenv import load_dotenv

load_dotenv()

GITHUB_API = os.getenv("GITHUB_API")


class GitHubService:
    def get_user_info(self, username: str):
        response = requests.get(f"{GITHUB_API}/users/{username}", timeout=(5, 10))

        if response.status_code != 200:
            raise Exception("GitHub user fetch failed")

        return response.json()

    def validate_user(self, username: str) -> bool:
        response = requests.get(f"{GITHUB_API}/users/{username}", timeout=(5, 10))
        return response.status_code == 200

    def fetch_events(self, username: str):
        events = []

        for page in range(1, 4):
            response = requests.get(
                f"{GITHUB_API}/users/{username}/events/public",
                params={"per_page": 100, "page": page},
                timeout=(5, 10),
            )

            if response.status_code != 200:
                raise Exception("GitHub events fetch failed")

            data = response.json()
            if not data:
                break

            events.extend(data)

        return events

    def fetch_repos(self, username: str):
        response = requests.get(f"{GITHUB_API}/users/{username}/repos", timeout=(5, 10))

        if response.status_code != 200:
            return []

        return response.json()
