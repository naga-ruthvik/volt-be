# ==============================================================================
# LEETCODE GRAPHQL QUERY CONSTANTS
# ==============================================================================

# ------------------------------------------------------------------------------
# TOPIC 1: USER PROFILES & PROGRESS METRICS
# ------------------------------------------------------------------------------

GET_USER_PROFILE_QUERY = """
query getUserProfile($username: String!) {
    allQuestionsCount {
        difficulty
        count
    }
    matchedUser(username: $username) {
        username
        githubUrl
        twitterUrl
        linkedinUrl
        contributions {
            points
            questionCount
            testcaseCount
        }
        profile {
            realName
            userAvatar
            birthday
            ranking
            reputation
            websites
            countryName
            company
            school
            skillTags
            aboutMe
            starRating
        }
        badges {
            id
            displayName
            icon
            creationDate
        }
        upcomingBadges {
            name
            icon
        }
        activeBadge {
            id
            displayName
            icon
            creationDate
        }
        submitStats {
            totalSubmissionNum {
                difficulty
                count
                submissions
            }
            acSubmissionNum {
                difficulty
                count
                submissions
            }
        }
        submissionCalendar
    }
    recentSubmissionList(username: $username, limit: 20) {
        title
        titleSlug
        timestamp
        statusDisplay
        lang
    }
}
"""

LANGUAGE_STATS_QUERY = """
query languageStats($username: String!) {
    matchedUser(username: $username) {
        languageProblemCount {
            languageName
            problemsSolved
        }
    }
}
"""

SKILL_STATS_QUERY = """
query skillStats($username: String!) {
  matchedUser(username: $username) {
    tagProblemCounts {
      advanced {
        tagName
        tagSlug
        problemsSolved
      }
      intermediate {
        tagName
        tagSlug
        problemsSolved
      }
      fundamental {
        tagName
        tagSlug
        problemsSolved
      }
    }
  }
}
"""

USER_QUESTION_PROGRESS_QUERY = """
query userProfileUserQuestionProgressV2($username: String!) {
    userProfileUserQuestionProgressV2(userSlug: $username) {
        numAcceptedQuestions {
            count
            difficulty
        }
        numFailedQuestions {
            count
            difficulty
        }
        numUntouchedQuestions {
            count
            difficulty
        }
        userSessionBeatsPercentage {
            difficulty
            percentage
        }
    }
}
"""


# ------------------------------------------------------------------------------
# TOPIC 2: SUBMISSIONS & HISTORICAL ACTIVITY
# ------------------------------------------------------------------------------

AC_SUBMISSION_QUERY = """
query getACSubmissions ($username: String!, $limit: Int) {
    recentAcSubmissionList(username: $username, limit: $limit) {
        title
        titleSlug
        timestamp
        statusDisplay
        lang
    }
}
"""

SUBMISSION_QUERY = """
query getRecentSubmissions($username: String!, $limit: Int) {
    recentSubmissionList(username: $username, limit: $limit) {
        title
        titleSlug
        timestamp
        statusDisplay
        lang
    }
}
"""

USER_PROFILE_CALENDAR_QUERY = """
query UserProfileCalendar($username: String!, $year: Int!) {
  matchedUser(username: $username) {
    userCalendar(year: $year) {
      activeYears
      streak
      totalActiveDays
      dccBadges {
        timestamp
        badge {
          name
          icon
        }
      }
      submissionCalendar
    }
  }
}
"""


# ------------------------------------------------------------------------------
# TOPIC 3: CONTESTS & COMPETITIVE RANKINGS
# ------------------------------------------------------------------------------

ALL_CONTESTS = """
query allContests {
    allContests {
        title
        titleSlug
        startTime
        duration
        originStartTime
        isVirtual
        containsPremium
    }
}
"""

USER_CONTEST_RANKING_INFO_QUERY = """
query userContestRankingInfo($username: String!) {
    userContestRanking(username: $username) {
        attendedContestsCount
        rating
        globalRanking
        totalParticipants
        topPercentage
        badge {
            name
        }
    }
    userContestRankingHistory(username: $username) {
        attended
        trendDirection
        problemsSolved
        totalProblems
        finishTimeInSeconds
        rating
        ranking
        contest {
            title
            startTime
        }
    }
}
"""


# ------------------------------------------------------------------------------
# TOPIC 4: PROBLEMS, SOLUTIONS & COMMUNITY DISCUSSIONS
# ------------------------------------------------------------------------------

DAILY_PROBLEM_QUERY = """
query getDailyProblem {
    activeDailyCodingChallengeQuestion {
        date
        link
        question {
            questionId
            questionFrontendId
            boundTopicId
            title
            titleSlug
            content
            translatedTitle
            translatedContent
            isPaidOnly
            difficulty
            likes
            dislikes
            isLiked
            similarQuestions
            exampleTestcases
            contributors {
                username
                profileUrl
                avatarUrl
            }
            topicTags {
                name
                slug
                translatedName
            }
            companyTagStats
            codeSnippets {
                lang
                langSlug
                code
            }
            stats
            hints
            solution {
                id
                canSeeDetail
                paidOnly
                hasVideoSolution
                paidOnlyVideo
            }
            status
            sampleTestCase
            metaData
            judgerAvailable
            judgeType
            mysqlSchemas
            enableRunCode
            enableTestMode
            enableDebugger
            envInfo
            libraryUrl
            adminUrl
            challengeQuestion {
                id
                date
                incompleteChallengeCount
                streakCount
                type
            }
            note
        }
    }
}
"""

DISCUSS_COMMENTS_QUERY = """
query discussComments($topicId: Int!, $orderBy: String = "newest_to_oldest", $pageNo: Int = 1, $numPerPage: Int = 10) {
    topicComments(topicId: $topicId, orderBy: $orderBy, pageNo: $pageNo, numPerPage: $numPerPage) {
        data {
            id
            pinned
            pinnedBy {
                username
            }
            post {
                ...DiscussPost
            }
            numChildren
        }
    }
}

fragment DiscussPost on PostNode {
    id
    voteCount
    voteStatus
    content
    updationDate
    creationDate
    status
    isHidden
    coinRewards {
        ...CoinReward
    }
    author {
        isDiscussAdmin
        isDiscussStaff
        username
        nameColor
        activeBadge {
            displayName
            icon
        }
        profile {
            userAvatar
            reputation
        }
        isActive
    }
    authorIsModerator
    isOwnPost
}

fragment CoinReward on ScoreNode {
    id
    score
    description
    date
}
"""

DISCUSS_TOPIC_QUERY = """
query DiscussTopic($topicId: Int!) {
    topic(id: $topicId) {
        id
        viewCount
        topLevelCommentCount
        subscribed
        title
        pinned
        tags
        hideFromTrending
        post {
            ...DiscussPost
        }
    }
}

fragment DiscussPost on PostNode {
    id
    voteCount
    voteStatus
    content
    updationDate
    creationDate
    status
    isHidden
    coinRewards {
        ...CoinReward
    }
    author {
        isDiscussAdmin
        isDiscussStaff
        username
        nameColor
        activeBadge {
            displayName
            icon
        }
        profile {
            userAvatar
            reputation
        }
        isActive
    }
    authorIsModerator
    isOwnPost
}

fragment CoinReward on ScoreNode {
    id
    score
    description
    date
}
"""

OFFICIAL_SOLUTION_QUERY = """
query OfficialSolution($titleSlug: String!) {
    question(titleSlug: $titleSlug) {
        solution {
            id
            title
            content
            contentTypeId
            paidOnly
            hasVideoSolution
            paidOnlyVideo
            canSeeDetail
            rating {
                count
                average
                userRating {
                    score
                }
            }
            topic {
                id
                commentCount
                topLevelCommentCount
                viewCount
                subscribed
                solutionTags {
                    name
                    slug
                }
                post {
                    id
                    status
                    creationDate
                    author {
                        username
                        isActive
                        profile {
                            userAvatar
                            reputation
                        }
                    }
                }
            }
        }
    }
}
"""

PROBLEM_LIST_QUERY = """
query getProblems($categorySlug: String, $limit: Int, $skip: Int, $filters: QuestionListFilterInput) {
    problemsetQuestionList: questionList(
        categorySlug: $categorySlug
        limit: $limit
        skip: $skip
        filters: $filters
    ) {
        total: totalNum
        questions: data {
            acRate
            difficulty
            freqBar
            questionFrontendId
            isFavor
            isPaidOnly
            status
            title
            titleSlug
            topicTags {
                name
                id
                slug
            }
            hasSolution
            hasVideoSolution
        }
    }
}
"""

SELECT_PROBLEM_QUERY = """
query selectProblem($titleSlug: String!) {
    question(titleSlug: $titleSlug) {
        questionId
        questionFrontendId
        boundTopicId
        title
        titleSlug
        content
        translatedTitle
        translatedContent
        isPaidOnly
        difficulty
        likes
        dislikes
        isLiked
        similarQuestions
        exampleTestcases
        contributors {
            username
            profileUrl
            avatarUrl
        }
        topicTags {
            name
            slug
            translatedName
        }
        companyTagStats
        codeSnippets {
            lang
            langSlug
            code
        }
        stats
        hints
        solution {
            id
            canSeeDetail
            paidOnly
            hasVideoSolution
            paidOnlyVideo
        }
        status
        sampleTestCase
        metaData
        judgerAvailable
        judgeType
        mysqlSchemas
        enableRunCode
        enableTestMode
        enableDebugger
        envInfo
        libraryUrl
        adminUrl
        challengeQuestion {
            id
            date
            incompleteChallengeCount
            streakCount
            type
        }
        note
    }
}
"""
