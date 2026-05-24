from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any

import requests

from ..errors import PlatformNetworkError, PlatformTimeoutError
from .queries import *  # noqa: F403

LEETCODE_USER_NOT_FOUND_MSG = "[LeetCode] API Error: User not found."
LEETCODE_USERNAME_REQUIRED_MSG = "[LeetCode] API Error: Username is required."

LEETCODE_GRAPHQL_URL = "https://leetcode.com/graphql"
LEETCODE_HEADERS = {
    "Content-Type": "application/json",
    "Referer": "https://leetcode.com",
}


def _error_payload(
    platform: str, error_type: str, message: str, details: dict | None = None
) -> dict:
    return {
        "status": "error",
        "platform": platform,
        "error_type": error_type,
        "message": message,
        "details": details or {},
    }


def _success_payload(platform: str, username: str | None, data: Any) -> dict:
    return {
        "status": "success",
        "platform": platform,
        "username": username,
        "data": data,
    }


def _build_fallback_id(
    platform: str, username: str, timestamp: str, event_type: str
) -> str:
    input_str = f"{platform}_{username}_{timestamp}_{event_type}"
    return hashlib.md5(input_str.encode("utf-8")).hexdigest()


def _normalize_username(username: str | None) -> str | None:
    return username if username else None


def _username_required_error(username: str | None) -> dict | None:
    if username:
        return None
    return _error_payload(
        "leetcode",
        "INVALID_USERNAME",
        LEETCODE_USERNAME_REQUIRED_MSG,
        {"username": username},
    )


def _to_iso_timestamp(timestamp: str | int | None) -> str | None:
    if timestamp is None:
        return None
    try:
        ts_int = int(timestamp)
    except (TypeError, ValueError):
        return None
    return datetime.fromtimestamp(ts_int, tz=timezone.utc).isoformat()


class LeetcodeClient:
    def __init__(self, base_url: str | None = None, timeout: tuple[int, int] = (5, 10)):
        self.base_url = base_url or LEETCODE_GRAPHQL_URL
        self.timeout = timeout

    def _post(self, query: str, variables: dict[str, Any]) -> dict:
        try:
            response = requests.post(
                self.base_url,
                headers=LEETCODE_HEADERS,
                json={"query": query, "variables": variables},
                timeout=self.timeout,
            )
        except requests.Timeout as exc:
            raise PlatformTimeoutError("LeetCode request timed out") from exc
        except requests.RequestException as exc:
            raise PlatformNetworkError("LeetCode request failed") from exc

        if response.status_code >= 500:
            raise PlatformNetworkError("LeetCode server error")

        try:
            return response.json()
        except ValueError as exc:
            raise PlatformNetworkError("LeetCode returned invalid JSON") from exc

    def _user_not_found_error(
        self,
        result: dict,
        username: str | None,
        details: dict | None = None,
        expect_user: bool = True,
    ) -> dict | None:
        if (
            expect_user and result.get("data", {}).get("matchedUser") is None
        ) or "errors" in result:
            details_payload = {"username": _normalize_username(username)}
            if details:
                details_payload.update(details)
            return _error_payload(
                "leetcode",
                "INVALID_USERNAME",
                LEETCODE_USER_NOT_FOUND_MSG,
                details_payload,
            )
        return None

    def _normalize_submissions(
        self, submissions: list[dict], username: str, event_type: str
    ) -> list[dict]:
        normalized = []
        for item in submissions:
            timestamp = item.get("timestamp")
            created_at = _to_iso_timestamp(timestamp)
            event_id = item.get("id")
            if event_id is None:
                slug = item.get("titleSlug") or item.get("title") or "submission"
                event_id = f"{slug}:{timestamp}" if timestamp else slug
            if event_id is None and created_at:
                event_id = _build_fallback_id(
                    "leetcode", username, created_at, event_type
                )

            normalized.append(
                {
                    "id": str(event_id) if event_id is not None else None,
                    "platform": "leetcode",
                    "created_at": created_at,
                    "event_type": event_type,
                    "title": item.get("title"),
                    "title_slug": item.get("titleSlug"),
                    "status": item.get("statusDisplay"),
                    "language": item.get("lang"),
                }
            )
        return normalized

    def get_user_profile(self, username: str) -> dict:
        missing_username = _username_required_error(username)
        if missing_username:
            return missing_username
        result = self._post(GET_USER_PROFILE_QUERY, {"username": username})
        error_payload = self._user_not_found_error(result, username)
        if error_payload:
            return error_payload

        data = result.get("data", {})
        matched_user = data.get("matchedUser", {})
        profile = matched_user.get("profile", {})

        badges = []
        for badge in matched_user.get("badges", []) or []:
            badges.append(
                {
                    "id": str(badge.get("id")) if badge.get("id") is not None else None,
                    "display_name": badge.get("displayName"),
                    "icon": badge.get("icon"),
                    "creation_date": badge.get("creationDate"),
                }
            )

        upcoming_badges = []
        for badge in matched_user.get("upcomingBadges", []) or []:
            badge_id = badge.get("name") or badge.get("icon")
            upcoming_badges.append(
                {
                    "id": str(badge_id) if badge_id is not None else None,
                    "name": badge.get("name"),
                    "icon": badge.get("icon"),
                }
            )

        active_badge = matched_user.get("activeBadge")
        active_badge_normalized = None
        if active_badge:
            active_badge_normalized = {
                "id": str(active_badge.get("id"))
                if active_badge.get("id") is not None
                else None,
                "display_name": active_badge.get("displayName"),
                "icon": active_badge.get("icon"),
                "creation_date": active_badge.get("creationDate"),
            }

        all_questions = []
        for entry in data.get("allQuestionsCount", []) or []:
            difficulty = entry.get("difficulty")
            all_questions.append(
                {
                    "id": str(difficulty) if difficulty is not None else None,
                    "difficulty": difficulty,
                    "count": entry.get("count"),
                }
            )

        submit_stats = matched_user.get("submitStats", {}) or {}
        total_submissions = []
        for entry in submit_stats.get("totalSubmissionNum", []) or []:
            difficulty = entry.get("difficulty")
            total_submissions.append(
                {
                    "id": str(difficulty) if difficulty is not None else None,
                    "difficulty": difficulty,
                    "count": entry.get("count"),
                    "submissions": entry.get("submissions"),
                }
            )
        accepted_submissions = []
        for entry in submit_stats.get("acSubmissionNum", []) or []:
            difficulty = entry.get("difficulty")
            accepted_submissions.append(
                {
                    "id": str(difficulty) if difficulty is not None else None,
                    "difficulty": difficulty,
                    "count": entry.get("count"),
                    "submissions": entry.get("submissions"),
                }
            )

        recent_submissions = self._normalize_submissions(
            data.get("recentSubmissionList", []) or [],
            username,
            "submission",
        )

        normalized = {
            "id": str(matched_user.get("username") or username),
            "platform": "leetcode",
            "username": matched_user.get("username") or username,
            "name": profile.get("realName"),
            "avatar": profile.get("userAvatar"),
            "ranking": profile.get("ranking"),
            "reputation": profile.get("reputation"),
            "country": profile.get("countryName"),
            "company": profile.get("company"),
            "school": profile.get("school"),
            "skill_tags": profile.get("skillTags"),
            "about_me": profile.get("aboutMe"),
            "star_rating": profile.get("starRating"),
            "github_url": matched_user.get("githubUrl"),
            "twitter_url": matched_user.get("twitterUrl"),
            "linkedin_url": matched_user.get("linkedinUrl"),
            "contributions": matched_user.get("contributions"),
            "badges": badges,
            "upcoming_badges": upcoming_badges,
            "active_badge": active_badge_normalized,
            "all_questions": all_questions,
            "submit_stats": {
                "total": total_submissions,
                "accepted": accepted_submissions,
            },
            "submission_calendar": matched_user.get("submissionCalendar"),
            "recent_submissions": recent_submissions,
        }
        return _success_payload("leetcode", _normalize_username(username), normalized)

    def get_language_stats(self, username: str) -> dict:
        missing_username = _username_required_error(username)
        if missing_username:
            return missing_username
        result = self._post(LANGUAGE_STATS_QUERY, {"username": username})
        error_payload = self._user_not_found_error(result, username)
        if error_payload:
            return error_payload

        data = result.get("data", {})
        matched_user = data.get("matchedUser", {}) or {}
        language_counts = []
        for entry in matched_user.get("languageProblemCount", []) or []:
            language_name = entry.get("languageName")
            language_counts.append(
                {
                    "id": str(language_name) if language_name is not None else None,
                    "language": language_name,
                    "problems_solved": entry.get("problemsSolved"),
                }
            )

        return _success_payload(
            "leetcode", _normalize_username(username), {"languages": language_counts}
        )

    def get_skill_stats(self, username: str) -> dict:
        missing_username = _username_required_error(username)
        if missing_username:
            return missing_username
        result = self._post(SKILL_STATS_QUERY, {"username": username})
        error_payload = self._user_not_found_error(result, username)
        if error_payload:
            return error_payload

        data = result.get("data", {})
        matched_user = data.get("matchedUser", {}) or {}
        tag_counts = matched_user.get("tagProblemCounts", {}) or {}

        def normalize_tags(items: list[dict]) -> list[dict]:
            normalized = []
            for entry in items or []:
                tag_slug = entry.get("tagSlug") or entry.get("tagName")
                normalized.append(
                    {
                        "id": str(tag_slug) if tag_slug is not None else None,
                        "tag": entry.get("tagName"),
                        "slug": entry.get("tagSlug"),
                        "problems_solved": entry.get("problemsSolved"),
                    }
                )
            return normalized

        normalized = {
            "fundamental": normalize_tags(tag_counts.get("fundamental", [])),
            "intermediate": normalize_tags(tag_counts.get("intermediate", [])),
            "advanced": normalize_tags(tag_counts.get("advanced", [])),
        }
        return _success_payload("leetcode", _normalize_username(username), normalized)

    def get_user_question_progress(self, username: str) -> dict:
        missing_username = _username_required_error(username)
        if missing_username:
            return missing_username
        result = self._post(USER_QUESTION_PROGRESS_QUERY, {"username": username})
        error_payload = self._user_not_found_error(result, username, expect_user=False)
        if error_payload:
            return error_payload

        progress = (
            result.get("data", {}).get("userProfileUserQuestionProgressV2", {}) or {}
        )

        def normalize_counts(items: list[dict]) -> list[dict]:
            normalized = []
            for entry in items or []:
                difficulty = entry.get("difficulty")
                normalized.append(
                    {
                        "id": str(difficulty) if difficulty is not None else None,
                        "difficulty": difficulty,
                        "count": entry.get("count"),
                        "percentage": entry.get("percentage"),
                    }
                )
            return normalized

        normalized = {
            "accepted": normalize_counts(progress.get("numAcceptedQuestions", [])),
            "failed": normalize_counts(progress.get("numFailedQuestions", [])),
            "untouched": normalize_counts(progress.get("numUntouchedQuestions", [])),
            "beats_percentage": normalize_counts(
                progress.get("userSessionBeatsPercentage", [])
            ),
        }
        return _success_payload("leetcode", _normalize_username(username), normalized)

    def get_submissions(self, username: str, limit: int | None = None) -> dict:
        missing_username = _username_required_error(username)
        if missing_username:
            return missing_username
        query_limit = limit if limit is not None else 20
        result = self._post(
            SUBMISSION_QUERY, {"username": username, "limit": query_limit}
        )
        error_payload = self._user_not_found_error(result, username, expect_user=False)
        if error_payload:
            return error_payload

        submissions = result.get("data", {}).get("recentSubmissionList", []) or []
        normalized = self._normalize_submissions(submissions, username, "submission")
        return _success_payload("leetcode", _normalize_username(username), normalized)

    def get_ac_submissions(self, username: str, limit: int | None = None) -> dict:
        missing_username = _username_required_error(username)
        if missing_username:
            return missing_username
        query_limit = limit if limit is not None else 20
        result = self._post(
            AC_SUBMISSION_QUERY, {"username": username, "limit": query_limit}
        )
        error_payload = self._user_not_found_error(result, username, expect_user=False)
        if error_payload:
            return error_payload

        submissions = result.get("data", {}).get("recentAcSubmissionList", []) or []
        normalized = self._normalize_submissions(
            submissions, username, "accepted_submission"
        )
        return _success_payload("leetcode", _normalize_username(username), normalized)

    def get_activity_summary(self, username: str) -> dict:
        missing_username = _username_required_error(username)
        if missing_username:
            return missing_username
        submissions_payload = self.get_submissions(username)
        if submissions_payload.get("status") == "error":
            return submissions_payload

        submissions = submissions_payload.get("data", [])
        activity_map: dict[str, int] = {}
        for item in submissions:
            created_at = item.get("created_at")
            if not created_at:
                continue
            date_key = created_at[:10]
            activity_map[date_key] = activity_map.get(date_key, 0) + 1

        summary = [
            {"platform": "leetcode", "date": date_key, "count": count}
            for date_key, count in sorted(activity_map.items())
        ]
        return _success_payload("leetcode", _normalize_username(username), summary)

    def get_user_profile_calendar(self, username: str, year: int) -> dict:
        missing_username = _username_required_error(username)
        if missing_username:
            return missing_username
        result = self._post(
            USER_PROFILE_CALENDAR_QUERY, {"username": username, "year": year}
        )
        error_payload = self._user_not_found_error(result, username)
        if error_payload:
            return error_payload

        calendar = (
            result.get("data", {}).get("matchedUser", {}).get("userCalendar", {}) or {}
        )
        dcc_badges = []
        for entry in calendar.get("dccBadges", []) or []:
            badge = entry.get("badge") or {}
            badge_id = entry.get("timestamp") or badge.get("name")
            dcc_badges.append(
                {
                    "id": str(badge_id) if badge_id is not None else None,
                    "timestamp": entry.get("timestamp"),
                    "badge": {
                        "name": badge.get("name"),
                        "icon": badge.get("icon"),
                    },
                }
            )

        normalized = {
            "active_years": calendar.get("activeYears"),
            "streak": calendar.get("streak"),
            "total_active_days": calendar.get("totalActiveDays"),
            "submission_calendar": calendar.get("submissionCalendar"),
            "dcc_badges": dcc_badges,
        }
        return _success_payload("leetcode", _normalize_username(username), normalized)

    def get_user_contest_ranking_info(self, username: str) -> dict:
        missing_username = _username_required_error(username)
        if missing_username:
            return missing_username
        result = self._post(USER_CONTEST_RANKING_INFO_QUERY, {"username": username})
        error_payload = self._user_not_found_error(result, username, expect_user=False)
        if error_payload:
            return error_payload

        data = result.get("data", {})
        ranking = data.get("userContestRanking", {}) or {}
        history = []
        for entry in data.get("userContestRankingHistory", []) or []:
            contest = entry.get("contest", {}) or {}
            contest_title = contest.get("title")
            start_time = contest.get("startTime")
            entry_id = (
                f"{contest_title}:{start_time}" if contest_title or start_time else None
            )
            history.append(
                {
                    "id": str(entry_id) if entry_id is not None else None,
                    "attended": entry.get("attended"),
                    "trend_direction": entry.get("trendDirection"),
                    "problems_solved": entry.get("problemsSolved"),
                    "total_problems": entry.get("totalProblems"),
                    "finish_time_seconds": entry.get("finishTimeInSeconds"),
                    "rating": entry.get("rating"),
                    "ranking": entry.get("ranking"),
                    "contest": {
                        "title": contest_title,
                        "start_time": start_time,
                    },
                }
            )

        normalized = {
            "ranking": ranking,
            "history": history,
        }
        return _success_payload("leetcode", _normalize_username(username), normalized)

    def get_all_contests(self, username: str | None = None) -> dict:
        result = self._post(ALL_CONTESTS, {})
        error_payload = self._user_not_found_error(result, username, expect_user=False)
        if error_payload:
            return error_payload

        contests = []
        for entry in result.get("data", {}).get("allContests", []) or []:
            contest_id = entry.get("titleSlug") or entry.get("title")
            contests.append(
                {
                    "id": str(contest_id) if contest_id is not None else None,
                    "title": entry.get("title"),
                    "title_slug": entry.get("titleSlug"),
                    "start_time": entry.get("startTime"),
                    "duration": entry.get("duration"),
                    "origin_start_time": entry.get("originStartTime"),
                    "is_virtual": entry.get("isVirtual"),
                    "contains_premium": entry.get("containsPremium"),
                }
            )

        return _success_payload("leetcode", _normalize_username(username), contests)

    def get_daily_problem(self, username: str | None = None) -> dict:
        result = self._post(DAILY_PROBLEM_QUERY, {})
        error_payload = self._user_not_found_error(result, username, expect_user=False)
        if error_payload:
            return error_payload

        data = (
            result.get("data", {}).get("activeDailyCodingChallengeQuestion", {}) or {}
        )
        question = data.get("question", {}) or {}
        topic_tags = []
        for entry in question.get("topicTags", []) or []:
            tag_id = entry.get("slug") or entry.get("name")
            topic_tags.append(
                {
                    "id": str(tag_id) if tag_id is not None else None,
                    "name": entry.get("name"),
                    "slug": entry.get("slug"),
                    "translated_name": entry.get("translatedName"),
                }
            )

        contributors = []
        for entry in question.get("contributors", []) or []:
            contributor_id = entry.get("username") or entry.get("profileUrl")
            contributors.append(
                {
                    "id": str(contributor_id) if contributor_id is not None else None,
                    "username": entry.get("username"),
                    "profile_url": entry.get("profileUrl"),
                    "avatar_url": entry.get("avatarUrl"),
                }
            )

        code_snippets = []
        for entry in question.get("codeSnippets", []) or []:
            snippet_id = entry.get("langSlug") or entry.get("lang")
            code_snippets.append(
                {
                    "id": str(snippet_id) if snippet_id is not None else None,
                    "language": entry.get("lang"),
                    "language_slug": entry.get("langSlug"),
                    "code": entry.get("code"),
                }
            )

        solution = question.get("solution")
        if solution:
            solution = {
                "id": str(solution.get("id"))
                if solution.get("id") is not None
                else None,
                "can_see_detail": solution.get("canSeeDetail"),
                "paid_only": solution.get("paidOnly"),
                "has_video_solution": solution.get("hasVideoSolution"),
                "paid_only_video": solution.get("paidOnlyVideo"),
            }

        normalized = {
            "date": data.get("date"),
            "link": data.get("link"),
            "question": {
                "id": str(question.get("questionId"))
                if question.get("questionId") is not None
                else None,
                "frontend_id": question.get("questionFrontendId"),
                "title": question.get("title"),
                "title_slug": question.get("titleSlug"),
                "content": question.get("content"),
                "difficulty": question.get("difficulty"),
                "is_paid_only": question.get("isPaidOnly"),
                "likes": question.get("likes"),
                "dislikes": question.get("dislikes"),
                "topic_tags": topic_tags,
                "contributors": contributors,
                "code_snippets": code_snippets,
                "solution": solution,
                "stats": question.get("stats"),
                "hints": question.get("hints"),
                "similar_questions": question.get("similarQuestions"),
                "example_testcases": question.get("exampleTestcases"),
            },
        }
        return _success_payload("leetcode", _normalize_username(username), normalized)

    def get_problem_list(
        self,
        tags: list[str] | None = None,
        difficulty: str | None = None,
        limit: int | None = None,
        skip: int | None = None,
        username: str | None = None,
    ) -> dict:
        query_limit = limit if limit is not None else 20
        query_skip = skip if skip is not None else 0
        filters: dict[str, Any] = {}
        if tags:
            filters["tags"] = tags
        if difficulty:
            filters["difficulty"] = difficulty

        result = self._post(
            PROBLEM_LIST_QUERY,
            {
                "categorySlug": "all-code-essentials",
                "limit": query_limit,
                "skip": query_skip,
                "filters": filters or {},
            },
        )
        error_payload = self._user_not_found_error(
            result,
            username,
            details={
                "tags": tags,
                "difficulty": difficulty,
                "limit": query_limit,
                "skip": query_skip,
            },
            expect_user=False,
        )
        if error_payload:
            return error_payload

        problem_list = result.get("data", {}).get("problemsetQuestionList", {}) or {}
        questions = []
        for entry in problem_list.get("questions", []) or []:
            tags_list = []
            for tag in entry.get("topicTags", []) or []:
                tag_id = tag.get("slug") or tag.get("name")
                tags_list.append(
                    {
                        "id": str(tag_id) if tag_id is not None else None,
                        "name": tag.get("name"),
                        "slug": tag.get("slug"),
                    }
                )

            question_id = entry.get("questionFrontendId") or entry.get("titleSlug")
            questions.append(
                {
                    "id": str(question_id) if question_id is not None else None,
                    "frontend_id": entry.get("questionFrontendId"),
                    "title": entry.get("title"),
                    "title_slug": entry.get("titleSlug"),
                    "difficulty": entry.get("difficulty"),
                    "ac_rate": entry.get("acRate"),
                    "is_paid_only": entry.get("isPaidOnly"),
                    "status": entry.get("status"),
                    "topic_tags": tags_list,
                    "has_solution": entry.get("hasSolution"),
                    "has_video_solution": entry.get("hasVideoSolution"),
                }
            )

        normalized = {
            "total": problem_list.get("total"),
            "questions": questions,
        }
        return _success_payload("leetcode", _normalize_username(username), normalized)

    def get_problem_by_slug(self, title_slug: str, username: str | None = None) -> dict:
        result = self._post(SELECT_PROBLEM_QUERY, {"titleSlug": title_slug})
        error_payload = self._user_not_found_error(
            result,
            username,
            details={"title_slug": title_slug},
            expect_user=False,
        )
        if error_payload:
            return error_payload

        question = result.get("data", {}).get("question", {}) or {}
        topic_tags = []
        for entry in question.get("topicTags", []) or []:
            tag_id = entry.get("slug") or entry.get("name")
            topic_tags.append(
                {
                    "id": str(tag_id) if tag_id is not None else None,
                    "name": entry.get("name"),
                    "slug": entry.get("slug"),
                    "translated_name": entry.get("translatedName"),
                }
            )

        contributors = []
        for entry in question.get("contributors", []) or []:
            contributor_id = entry.get("username") or entry.get("profileUrl")
            contributors.append(
                {
                    "id": str(contributor_id) if contributor_id is not None else None,
                    "username": entry.get("username"),
                    "profile_url": entry.get("profileUrl"),
                    "avatar_url": entry.get("avatarUrl"),
                }
            )

        code_snippets = []
        for entry in question.get("codeSnippets", []) or []:
            snippet_id = entry.get("langSlug") or entry.get("lang")
            code_snippets.append(
                {
                    "id": str(snippet_id) if snippet_id is not None else None,
                    "language": entry.get("lang"),
                    "language_slug": entry.get("langSlug"),
                    "code": entry.get("code"),
                }
            )

        solution = question.get("solution")
        if solution:
            solution = {
                "id": str(solution.get("id"))
                if solution.get("id") is not None
                else None,
                "can_see_detail": solution.get("canSeeDetail"),
                "paid_only": solution.get("paidOnly"),
                "has_video_solution": solution.get("hasVideoSolution"),
                "paid_only_video": solution.get("paidOnlyVideo"),
            }

        challenge = question.get("challengeQuestion")
        if challenge:
            challenge = {
                "id": str(challenge.get("id"))
                if challenge.get("id") is not None
                else None,
                "date": challenge.get("date"),
                "incomplete_challenge_count": challenge.get("incompleteChallengeCount"),
                "streak_count": challenge.get("streakCount"),
                "type": challenge.get("type"),
            }

        normalized = {
            "id": str(question.get("questionId"))
            if question.get("questionId") is not None
            else None,
            "frontend_id": question.get("questionFrontendId"),
            "title": question.get("title"),
            "title_slug": question.get("titleSlug"),
            "content": question.get("content"),
            "difficulty": question.get("difficulty"),
            "likes": question.get("likes"),
            "dislikes": question.get("dislikes"),
            "is_paid_only": question.get("isPaidOnly"),
            "stats": question.get("stats"),
            "hints": question.get("hints"),
            "similar_questions": question.get("similarQuestions"),
            "topic_tags": topic_tags,
            "contributors": contributors,
            "code_snippets": code_snippets,
            "solution": solution,
            "challenge_question": challenge,
        }
        return _success_payload("leetcode", _normalize_username(username), normalized)

    def get_official_solution(
        self, title_slug: str, username: str | None = None
    ) -> dict:
        result = self._post(OFFICIAL_SOLUTION_QUERY, {"titleSlug": title_slug})
        error_payload = self._user_not_found_error(
            result,
            username,
            details={"title_slug": title_slug},
            expect_user=False,
        )
        if error_payload:
            return error_payload

        solution = result.get("data", {}).get("question", {}).get("solution") or {}
        topic = solution.get("topic") or {}
        solution_tags = []
        for entry in topic.get("solutionTags", []) or []:
            tag_id = entry.get("slug") or entry.get("name")
            solution_tags.append(
                {
                    "id": str(tag_id) if tag_id is not None else None,
                    "name": entry.get("name"),
                    "slug": entry.get("slug"),
                }
            )

        normalized = {
            "id": str(solution.get("id")) if solution.get("id") is not None else None,
            "title": solution.get("title"),
            "content": solution.get("content"),
            "content_type_id": solution.get("contentTypeId"),
            "paid_only": solution.get("paidOnly"),
            "has_video_solution": solution.get("hasVideoSolution"),
            "paid_only_video": solution.get("paidOnlyVideo"),
            "can_see_detail": solution.get("canSeeDetail"),
            "rating": solution.get("rating"),
            "topic": {
                "id": str(topic.get("id")) if topic.get("id") is not None else None,
                "comment_count": topic.get("commentCount"),
                "top_level_comment_count": topic.get("topLevelCommentCount"),
                "view_count": topic.get("viewCount"),
                "subscribed": topic.get("subscribed"),
                "solution_tags": solution_tags,
                "post": topic.get("post"),
            },
        }
        return _success_payload("leetcode", _normalize_username(username), normalized)

    def get_discuss_topic(self, topic_id: int, username: str | None = None) -> dict:
        result = self._post(DISCUSS_TOPIC_QUERY, {"topicId": topic_id})
        error_payload = self._user_not_found_error(
            result,
            username,
            details={"topic_id": topic_id},
            expect_user=False,
        )
        if error_payload:
            return error_payload

        topic = result.get("data", {}).get("topic", {}) or {}
        normalized = {
            "id": str(topic.get("id")) if topic.get("id") is not None else None,
            "title": topic.get("title"),
            "view_count": topic.get("viewCount"),
            "top_level_comment_count": topic.get("topLevelCommentCount"),
            "subscribed": topic.get("subscribed"),
            "pinned": topic.get("pinned"),
            "tags": topic.get("tags"),
            "hide_from_trending": topic.get("hideFromTrending"),
            "post": topic.get("post"),
        }
        return _success_payload("leetcode", _normalize_username(username), normalized)

    def get_discuss_comments(
        self,
        topic_id: int,
        order_by: str = "newest_to_oldest",
        page_no: int = 1,
        num_per_page: int = 10,
        username: str | None = None,
    ) -> dict:
        result = self._post(
            DISCUSS_COMMENTS_QUERY,
            {
                "topicId": topic_id,
                "orderBy": order_by,
                "pageNo": page_no,
                "numPerPage": num_per_page,
            },
        )
        error_payload = self._user_not_found_error(
            result,
            username,
            details={
                "topic_id": topic_id,
                "order_by": order_by,
                "page_no": page_no,
                "num_per_page": num_per_page,
            },
            expect_user=False,
        )
        if error_payload:
            return error_payload

        comments = []
        for entry in (
            result.get("data", {}).get("topicComments", {}).get("data", []) or []
        ):
            entry_id = entry.get("id")
            comments.append(
                {
                    "id": str(entry_id) if entry_id is not None else None,
                    "pinned": entry.get("pinned"),
                    "pinned_by": entry.get("pinnedBy"),
                    "post": entry.get("post"),
                    "num_children": entry.get("numChildren"),
                }
            )

        return _success_payload("leetcode", _normalize_username(username), comments)
