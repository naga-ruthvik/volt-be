# ruff: noqa
from pprint import pprint

from ..platforms import CodeforcesClient, GitHubClient


class GitHubClientTest:
    client = GitHubClient()

    def test_all_apis(self):
        print("---------------- USER ----------------")
        res = self.client.get_user_info("naga-ruthvik")
        pprint(res)

        print("---------------- REPO ----------------")
        res = self.client.get_repos("naga-ruthvik")
        pprint(res)

        print("---------------- VALIDATE ----------------")
        res = self.client.get_user_exists("naga-ruthvik")
        pprint(res)

        print("---------------- EVENTS ----------------")
        res = self.client.get_events("naga-ruthvik")
        pprint(res)

        print("--------------- SUMMARY ---------------")
        res = self.client.get_activity_summary("naga-ruthvik")
        pprint(res)


class CodeforcesAPITest:
    client = CodeforcesClient()

    def test_all_apis(self):
        print("---------------- USER ----------------")
        res = self.client.get_user_info("naga_ruthvik")
        pprint(res)

        print("---------------- VALIDATE ----------------")
        res = self.client.get_user_exists("naga_ruthvik")
        pprint(res)

        print("---------------- ACTIVITIES ----------------")
        res = self.client.get_activities("naga_ruthvik")
        pprint(res)

        print("--------------- SUMMARY ---------------")
        res = self.client.get_activity_summary("naga_ruthvik")
        pprint(res)


if __name__ == "__main__":
    codeforces = CodeforcesAPITest()
    codeforces.test_all_apis()
