from __future__ import annotations

import math
from typing import Sequence


def accepted_rating_update(current_rating: float, problem_rating: int, k_factor: float) -> float:
    expected = 1.0 / (1.0 + 10 ** ((problem_rating - current_rating) / 400.0))
    return current_rating + k_factor * (1.0 - expected)


RATING_SCORE_BASE = 1500
RATING_SCORE_STEP = 200
RATING_SCORE_FACTOR = 4.0


def leaderboard_rating(solved_ratings: Sequence[int], fallback_rating: float = 0.0) -> float:
    if not solved_ratings:
        return fallback_rating
    points = sum(problem_rating_points(rating) for rating in solved_ratings)
    return RATING_SCORE_BASE + RATING_SCORE_STEP * math.log(points, RATING_SCORE_FACTOR)


def problem_rating_points(problem_rating: int) -> float:
    return RATING_SCORE_FACTOR ** ((int(problem_rating) - RATING_SCORE_BASE) / RATING_SCORE_STEP)
