from __future__ import annotations


def accepted_rating_update(current_rating: float, problem_rating: int, k_factor: float) -> float:
    expected = 1.0 / (1.0 + 10 ** ((problem_rating - current_rating) / 400.0))
    return current_rating + k_factor * (1.0 - expected)
