from __future__ import annotations

import random
from typing import Iterable, Iterator, Optional, Sequence, Set

from .models import CFProblem


class ProblemSelector:
    def __init__(
        self,
        min_rating: int = 1900,
        max_rating: int = 2600,
        recent_pool_size: int = 500,
    ) -> None:
        self.min_rating = min_rating
        self.max_rating = max_rating
        self.recent_pool_size = max(1, recent_pool_size)
        self._random = random.SystemRandom()

    def candidates(
        self,
        problems: Iterable[CFProblem],
        sent_ids: Set[str],
        min_rating: Optional[int] = None,
        max_rating: Optional[int] = None,
    ) -> Sequence[CFProblem]:
        lower = self.min_rating if min_rating is None else min_rating
        upper = self.max_rating if max_rating is None else max_rating
        return [
            problem
            for problem in problems
            if lower <= problem.rating <= upper and problem.cf_id not in sent_ids
        ]

    def shuffled_candidates(
        self,
        problems: Iterable[CFProblem],
        sent_ids: Set[str],
        min_rating: Optional[int] = None,
        max_rating: Optional[int] = None,
    ) -> Iterator[CFProblem]:
        pool = list(self.candidates(problems, sent_ids, min_rating, max_rating))
        pool.sort(key=lambda problem: (problem.contest_id, problem.index), reverse=True)
        pool = pool[: self.recent_pool_size]
        self._random.shuffle(pool)
        return iter(pool)
