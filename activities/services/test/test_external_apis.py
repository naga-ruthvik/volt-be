# ruff: noqa
from pprint import pprint
from ..platforms.github_service import GitHubService
from ..platforms.codeforces_service import CodeforcesService
from ..normalization import ActivityNormalization


class GitHubServiceTest:
    service = GitHubService()

    def test_all_apis(self):
        print("---------------- USER ----------------")
        res = self.service.get_user_info("naga-ruthvik")
        pprint(res)

        print("---------------- REPO ----------------")
        res = self.service.fetch_repos("naga-ruthvik")
        pprint(res)

        print("---------------- VALIDATE ----------------")
        res = self.service.validate_user("naga-ruthvik")
        pprint(res)

        print("---------------- EVENTS ----------------")
        res = self.service.fetch_events("naga-ruthvik")
        pprint(res)


class CodeforcesAPITest:
    service = CodeforcesService()
    normalization = ActivityNormalization()

    def test_all_apis(self):
        print("---------------- USER ----------------")
        res = self.service.get_user_info("naga_ruthvik")
        pprint(res)

        print("---------------- VALIDATE ----------------")
        res = self.service.validate_user("naga_ruthvik")
        pprint(res)

        print("---------------- ACTIVITIES ----------------")
        res = self.service.fetch_activities("naga_ruthvik")
        pprint(res)

        print("---------------NORMALIZATION-----------")
        res = self.normalization.codeforces_activity_normalizer(res)
        pprint(res)


if __name__ == "__main__":
    codeforces = CodeforcesAPITest()
    codeforces.test_all_apis()
