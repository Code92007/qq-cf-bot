from __future__ import annotations

import json
import logging
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Iterable, List, Optional

from .cf_mirrors import codeforces_url_variants, normalize_codeforces_base_urls
from .models import CFContest, CFProblem


LOGGER = logging.getLogger(__name__)


class CodeforcesClient:
    def __init__(
        self,
        cache_path: Path,
        cache_ttl_seconds: int = 6 * 60 * 60,
        base_urls: Iterable[str] | str | None = None,
    ) -> None:
        self.cache_path = cache_path
        self.cache_ttl_seconds = cache_ttl_seconds
        self.base_urls = normalize_codeforces_base_urls(base_urls)

    def fetch_problems(self) -> List[CFProblem]:
        payload = self._load_fresh_cache()
        if payload is None:
            try:
                payload = self._fetch_remote()
                self._save_cache(payload)
            except (OSError, urllib.error.URLError, TimeoutError, RuntimeError):
                payload = self._load_any_cache()
                if payload is None:
                    raise
        return list(_parse_problemset(payload))

    def resolve_problem(self, contest_id: int, index: str) -> Optional[CFProblem]:
        problems = self.fetch_problems()
        normalized_index = index.upper()
        direct = _find_problem(problems, contest_id, normalized_index)
        if direct is not None:
            return direct

        # The global problemset only contains the canonical Div. 1 id for
        # shared Div. 1/Div. 2 problems. Contest standings retain aliases such
        # as 2263C2, which is published globally as 2262A2.
        payload = _fetch_json_from_codeforces_variants(
            f"/api/contest.standings?contestId={contest_id}",
            self.base_urls,
            timeout_seconds=20,
        )
        contest_problem = _find_problem(_parse_problemset(payload), contest_id, normalized_index)
        if contest_problem is None:
            return None

        canonical_candidates = [
            problem
            for problem in problems
            if problem.name == contest_problem.name and problem.rating == contest_problem.rating
        ]
        if canonical_candidates:
            return min(
                canonical_candidates,
                key=lambda problem: (abs(problem.contest_id - contest_id), problem.contest_id, problem.index),
            )
        return contest_problem

    def fetch_contests(self, gym: bool = False) -> List[CFContest]:
        query = urllib.parse.urlencode({"gym": "true" if gym else "false"})
        payload = _fetch_json_from_codeforces_variants(
            f"/api/contest.list?{query}",
            self.base_urls,
            timeout_seconds=20,
        )
        return list(_parse_contests(payload, gym=gym))

    def fetch_contest(self, contest_id: int) -> tuple[CFContest, List[CFProblem]]:
        # Public non-gym standings now reject every query parameter except contestId.
        query_params = {"contestId": contest_id}
        if contest_id >= 100_000:
            query_params.update({"from": 1, "count": 1})
        query = urllib.parse.urlencode(query_params)
        payload = _fetch_json_from_codeforces_variants(
            f"/api/contest.standings?{query}",
            self.base_urls,
            timeout_seconds=20,
        )
        result = payload.get("result") or {}
        raw_contest = result.get("contest") or {}
        if not raw_contest or int(raw_contest.get("id") or 0) != contest_id:
            raise RuntimeError(f"Codeforces contest {contest_id} was not found")
        contest = _contest_from_json(raw_contest, gym=contest_id >= 100_000)
        problems = list(_parse_contest_problems(result.get("problems") or (), is_gym=contest.is_gym))
        if not problems:
            raise RuntimeError(f"Codeforces contest {contest_id} has no public problems")
        if not contest.is_gym:
            try:
                catalog = self.fetch_problems()
                problems = [_canonical_problem(problem, catalog) for problem in problems]
            except Exception as exc:
                LOGGER.warning("failed to canonicalize contest %s problems: %s", contest_id, exc)
        return contest, problems

    def _fetch_remote(self) -> dict:
        return _fetch_json_from_codeforces_variants("/api/problemset.problems", self.base_urls, timeout_seconds=20)

    def _load_fresh_cache(self) -> Optional[dict]:
        if not self.cache_path.exists():
            return None
        if time.time() - self.cache_path.stat().st_mtime > self.cache_ttl_seconds:
            return None
        return self._load_any_cache()

    def _load_any_cache(self) -> Optional[dict]:
        if not self.cache_path.exists():
            return None
        with self.cache_path.open("r", encoding="utf-8") as file:
            return json.load(file)

    def _save_cache(self, payload: dict) -> None:
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self.cache_path.with_suffix(".tmp")
        with tmp_path.open("w", encoding="utf-8") as file:
            json.dump(payload, file, ensure_ascii=False)
        tmp_path.replace(self.cache_path)


def _parse_problemset(payload: dict) -> Iterable[CFProblem]:
    if payload.get("status") != "OK":
        raise RuntimeError(f"Codeforces API returned non-OK status: {payload.get('status')!r}")

    result = payload.get("result") or {}
    for raw in result.get("problems") or []:
        contest_id = raw.get("contestId")
        index = raw.get("index")
        name = raw.get("name")
        rating = raw.get("rating")
        if contest_id is None or not index or not name or rating is None:
            continue
        yield CFProblem(
            contest_id=int(contest_id),
            index=str(index),
            name=str(name),
            rating=int(rating),
            tags=tuple(str(tag) for tag in raw.get("tags") or ()),
            is_gym=int(contest_id) >= 100_000,
        )


def _parse_contests(payload: dict, gym: bool = False) -> Iterable[CFContest]:
    if payload.get("status") != "OK":
        raise RuntimeError(f"Codeforces API returned non-OK status: {payload.get('status')!r}")
    for raw in payload.get("result") or []:
        if raw.get("id") is None or not raw.get("name"):
            continue
        yield _contest_from_json(raw, gym=gym)


def _contest_from_json(raw: dict, gym: bool = False) -> CFContest:
    start = raw.get("startTimeSeconds")
    return CFContest(
        contest_id=int(raw["id"]),
        name=str(raw["name"]),
        phase=str(raw.get("phase") or ""),
        duration_seconds=max(0, int(raw.get("durationSeconds") or 0)),
        start_time_seconds=int(start) if start is not None else None,
        is_gym=bool(gym or int(raw["id"]) >= 100_000),
    )


def _parse_contest_problems(raw_problems: Iterable[dict], is_gym: bool = False) -> Iterable[CFProblem]:
    for raw in raw_problems:
        contest_id = raw.get("contestId")
        index = raw.get("index")
        name = raw.get("name")
        if contest_id is None or not index or not name:
            continue
        yield CFProblem(
            contest_id=int(contest_id),
            index=str(index),
            name=str(name),
            rating=int(raw.get("rating") or 0),
            tags=tuple(str(tag) for tag in raw.get("tags") or ()),
            is_gym=is_gym,
        )


def _find_problem(problems: Iterable[CFProblem], contest_id: int, index: str) -> Optional[CFProblem]:
    normalized_index = index.upper()
    for problem in problems:
        if problem.contest_id == contest_id and problem.index.upper() == normalized_index:
            return problem
    return None


def _canonical_problem(problem: CFProblem, catalog: Iterable[CFProblem]) -> CFProblem:
    problem_list = list(catalog)
    direct = _find_problem(problem_list, problem.contest_id, problem.index)
    if direct is not None:
        return direct
    candidates = [
        item
        for item in problem_list
        if item.name == problem.name and item.rating == problem.rating
    ]
    if not candidates:
        return problem
    return min(
        candidates,
        key=lambda item: (abs(item.contest_id - problem.contest_id), item.contest_id, item.index),
    )


class CodeforcesStatusClient:
    def __init__(
        self,
        handle: str,
        timeout_seconds: int = 30,
        base_urls: Iterable[str] | str | None = None,
    ) -> None:
        self.handle = handle
        self.timeout_seconds = timeout_seconds
        self.base_urls = normalize_codeforces_base_urls(base_urls)

    def fetch_recent(self, count: int = 10) -> List[dict]:
        if not self.handle:
            raise RuntimeError("Codeforces handle is not configured")
        query = urllib.parse.urlencode({"handle": self.handle, "from": 1, "count": count})
        payload = _fetch_json_from_codeforces_variants(
            f"/api/user.status?{query}",
            self.base_urls,
            timeout_seconds=self.timeout_seconds,
        )
        if payload.get("status") != "OK":
            raise RuntimeError(f"Codeforces user.status returned non-OK status: {payload.get('status')!r}")
        return list(payload.get("result") or [])


def _fetch_json_from_codeforces_variants(
    path_or_url: str,
    base_urls: Iterable[str] | str | None,
    timeout_seconds: int,
) -> dict:
    errors = []
    for index, url in enumerate(codeforces_url_variants(path_or_url, base_urls)):
        request = urllib.request.Request(
            url,
            headers={"User-Agent": "qq-cf-bot/0.1"},
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
            if payload.get("status") != "OK":
                raise RuntimeError(f"non-OK status {payload.get('status')!r}")
            if index > 0:
                LOGGER.info("Codeforces API succeeded via fallback mirror: %s", url)
            return payload
        except Exception as exc:
            LOGGER.warning("Codeforces API candidate failed url=%s error=%s", url, exc)
            errors.append(f"{url}: {exc}")
    raise RuntimeError("Codeforces API failed for all configured mirrors: " + "; ".join(errors))
