from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Iterable, List, Optional

from .models import CFProblem


CODEFORCES_PROBLEMSET_URL = "https://codeforces.com/api/problemset.problems"
CODEFORCES_USER_STATUS_URL = "https://codeforces.com/api/user.status"


class CodeforcesClient:
    def __init__(self, cache_path: Path, cache_ttl_seconds: int = 6 * 60 * 60) -> None:
        self.cache_path = cache_path
        self.cache_ttl_seconds = cache_ttl_seconds

    def fetch_problems(self) -> List[CFProblem]:
        payload = self._load_fresh_cache()
        if payload is None:
            try:
                payload = self._fetch_remote()
                self._save_cache(payload)
            except (OSError, urllib.error.URLError, TimeoutError):
                payload = self._load_any_cache()
                if payload is None:
                    raise
        return list(_parse_problemset(payload))

    def _fetch_remote(self) -> dict:
        request = urllib.request.Request(
            CODEFORCES_PROBLEMSET_URL,
            headers={"User-Agent": "qq-cf-bot/0.1"},
        )
        with urllib.request.urlopen(request, timeout=20) as response:
            return json.loads(response.read().decode("utf-8"))

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
        )


class CodeforcesStatusClient:
    def __init__(self, handle: str, timeout_seconds: int = 30) -> None:
        self.handle = handle
        self.timeout_seconds = timeout_seconds

    def fetch_recent(self, count: int = 10) -> List[dict]:
        if not self.handle:
            raise RuntimeError("Codeforces handle is not configured")
        query = urllib.parse.urlencode({"handle": self.handle, "from": 1, "count": count})
        request = urllib.request.Request(
            f"{CODEFORCES_USER_STATUS_URL}?{query}",
            headers={"User-Agent": "qq-cf-bot/0.1"},
        )
        with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
            payload = json.loads(response.read().decode("utf-8"))
        if payload.get("status") != "OK":
            raise RuntimeError(f"Codeforces user.status returned non-OK status: {payload.get('status')!r}")
        return list(payload.get("result") or [])
