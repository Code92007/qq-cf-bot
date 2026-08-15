from __future__ import annotations

import json
import re
import urllib.error
import urllib.parse
import urllib.request
from html import unescape
from typing import Any, Iterable, Optional, Tuple

from .models import CFProblem, ProblemStatement


_FE_JSON_RE = re.compile(
    r"window\._feInjection\s*=\s*JSON\.parse\(decodeURIComponent\((?P<quote>['\"])(?P<data>.+?)(?P=quote)\)\)",
    re.DOTALL,
)


class LuoguClient:
    def fetch_statement(self, problem: CFProblem) -> ProblemStatement:
        url = f"https://www.luogu.com.cn/problem/{problem.luogu_pid}"
        payload = self._fetch_json(url)
        current_data = payload.get("currentData") or payload.get("data", {}).get("currentData") or {}
        raw_problem = current_data.get("problem") or payload.get("problem")
        if not isinstance(raw_problem, dict):
            raise RuntimeError(f"Luogu response for {problem.luogu_pid} does not contain currentData.problem")
        statement = statement_from_luogu_problem(raw_problem, fallback_title=problem.name, source_url=url)
        if not statement.description and not statement.input_format and not statement.output_format:
            raise RuntimeError(f"Luogu statement for {problem.luogu_pid} is empty")
        return statement

    def fetch_solution_payload(self, problem: CFProblem) -> dict:
        url = f"https://www.luogu.com.cn/problem/solution/{problem.luogu_pid}"
        return self._fetch_json(url)

    def _fetch_json(self, url: str) -> dict:
        headers = {
            "User-Agent": "qq-cf-bot/0.1",
            "Accept": "application/json, text/plain, */*",
            "Referer": "https://www.luogu.com.cn/problem/list",
            "X-Requested-With": "XMLHttpRequest",
            "x-lentille-request": "content-only",
            "x-luogu-type": "content-only",
        }
        request = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                text = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            raise RuntimeError(f"Luogu returned HTTP {exc.code} for {url}") from exc

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            injected = _extract_fe_injection(text)
            if injected is not None:
                return injected
            raise RuntimeError("Luogu response is neither JSON nor a recognizable injected data page")


def _extract_fe_injection(html: str) -> Optional[dict]:
    match = _FE_JSON_RE.search(html)
    if not match:
        return None
    text = urllib.parse.unquote(match.group("data"))
    return json.loads(unescape(text))


def statement_from_luogu_problem(raw: dict, fallback_title: str, source_url: str) -> ProblemStatement:
    samples = list(_normalize_samples(raw.get("samples") or ()))
    return ProblemStatement(
        pid=str(raw.get("pid") or ""),
        title=str(raw.get("title") or fallback_title),
        background=str(raw.get("background") or ""),
        description=str(raw.get("description") or raw.get("content") or ""),
        input_format=str(raw.get("inputFormat") or raw.get("input_format") or ""),
        output_format=str(raw.get("outputFormat") or raw.get("output_format") or ""),
        samples=samples,
        hint=str(raw.get("hint") or ""),
        source_url=source_url,
    )


def _normalize_samples(raw_samples: Iterable[Any]) -> Iterable[Tuple[str, str]]:
    for sample in raw_samples:
        if isinstance(sample, dict):
            yield str(sample.get("input") or ""), str(sample.get("output") or "")
        elif isinstance(sample, (list, tuple)) and len(sample) >= 2:
            yield str(sample[0]), str(sample[1])
