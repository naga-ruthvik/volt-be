import os

import requests
from dotenv import load_dotenv

load_dotenv()

CODEFORCES_API = os.getenv("CODEFORCES_API")


class CodeforcesService:
    def get_user_info(self, username: str):
        url = CODEFORCES_API + f"user.info?handles={username}"
        response = requests.get(url)
        response_data = response.json()
        if response.status_code != 200 or response_data["status"] != "OK":
            raise Exception("Codeforces user fetch failed")
        return response

    def validate_user(self, username: str):
        url = CODEFORCES_API + f"user.info?handles={username}"
        response = requests.get(url)
        return response.status_code == 200 and response.json()["status"] == "OK"

    def fetch_activities(self, username: str):
        url = CODEFORCES_API + f"user.status?handle={username}"
        response = requests.get(url)
        return response.json()
