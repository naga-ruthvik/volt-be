def error_payload(error_type: str, message: str, details: dict | None = None) -> dict:
    return {
        "status": "error",
        "platform": "HACKER RANK",
        "error_type": error_type,
        "message": message,
        "details": details or {},
    }


def success_payload(username: str, data: dict | list) -> dict:
    return {
        "status": "success",
        "platform": "HACKER RANK",
        "username": username,
        "data": data,
    }


def _calculate_percentage(current: int, total: int) -> float:
    if total == 0:
        return 0.0
    return round((current / total) * 100, 2)


def build_metrics(models: list[dict]) -> dict:
    questions_solved = 0
    current_points = 0
    total_points = 0
    total_challenges = 0
    stars_earned = 0
    possible_stars = 0
    best_rank = None
    badges = []

    if not isinstance(models, list):
        return {}

    for model in models:
        if not isinstance(model, dict):
            continue

        questions_solved += model.get("solved", 0)
        current_points += model.get("current_points", 0)
        total_points += model.get("total_points", 0)
        total_challenges += model.get("total_challenges", 0)
        stars_earned += model.get("stars", 0)
        possible_stars += model.get("total_stars", 0)

        rank = model.get("hacker_rank")
        if rank is not None and (best_rank is None or rank < best_rank):
            best_rank = rank

        badges.append(
            {
                "name": model.get("badge_name"),
                "type": model.get("badge_type"),
                "category": model.get("category_name"),
                "stars": model.get("stars", 0),
                "max_stars": model.get("total_stars", 0),
                "points": model.get("current_points", 0),
                "max_points": model.get("total_points", 0),
                "solved": model.get("solved", 0),
                "total_challenges": model.get("total_challenges", 0),
                "rank": model.get("hacker_rank"),
                "level": model.get("level"),
            }
        )

    return {
        "questions_solved": questions_solved,
        "points_earned": current_points,
        "total_available_points": total_points,
        "total_challenges": total_challenges,
        "stars_earned": stars_earned,
        "possible_stars": possible_stars,
        "best_rank": best_rank,
        "domains_count": len(models),
        "points_completion_percentage": _calculate_percentage(
            current_points, total_points
        ),
        "star_completion_percentage": _calculate_percentage(
            stars_earned, possible_stars
        ),
        "badges": badges,
    }
