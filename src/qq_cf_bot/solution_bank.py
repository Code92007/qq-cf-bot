from __future__ import annotations

import hashlib
import html
import logging
import re
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any, Iterable, List, Optional

from .luogu import LuoguClient
from .models import CFProblem, SolutionReference
from .storage import SentProblemStore
from .submitter import CodeforcesRemoteJudge


LOGGER = logging.getLogger(__name__)


class SolutionBank:
    def __init__(
        self,
        store: SentProblemStore,
        luogu: LuoguClient,
        remote_judge: CodeforcesRemoteJudge,
        enabled: bool = True,
        min_refs: int = 1,
        max_refs: int = 4,
        max_ref_chars: int = 5000,
        fetch_luogu: bool = True,
        fetch_cf_editorial: bool = True,
        fetch_cf_ac_code: bool = False,
    ) -> None:
        self.store = store
        self.luogu = luogu
        self.remote_judge = remote_judge
        self.enabled = enabled
        self.min_refs = max(0, min_refs)
        self.max_refs = max(0, max_refs)
        self.max_ref_chars = max(500, max_ref_chars)
        self.fetch_luogu = fetch_luogu
        self.fetch_cf_editorial = fetch_cf_editorial
        self.fetch_cf_ac_code = fetch_cf_ac_code

    def ensure(self, problem: CFProblem) -> List[SolutionReference]:
        cached = self.store.list_solution_references(problem.cf_id)
        if not self.enabled or len(cached) >= self.min_refs:
            return cached[: self.max_refs]
        if self.store.get_solution_fetch_attempt(problem.cf_id):
            return cached[: self.max_refs]

        references: List[SolutionReference] = []
        if self.fetch_luogu:
            references.extend(self._fetch_luogu(problem))
        if self.fetch_cf_editorial:
            references.extend(self._fetch_codeforces_editorial(problem))
        if self.fetch_cf_ac_code and self.remote_judge.configured:
            try:
                references.extend(
                    self.remote_judge.fetch_accepted_code_references(
                        problem,
                        max_items=max(1, self.max_refs - len(references)),
                        max_chars=self.max_ref_chars,
                    )
                )
            except Exception as exc:
                LOGGER.warning("failed to fetch Codeforces AC code for %s: %s", problem.cf_id, exc)

        self.store.add_solution_references(_dedupe_references(references)[: self.max_refs])
        self.store.mark_solution_fetch_attempt(problem.cf_id)
        return self.store.list_solution_references(problem.cf_id)[: self.max_refs]

    def context_for_prompt(self, references: Iterable[SolutionReference], max_chars: int) -> str:
        chunks = []
        used = 0
        for index, reference in enumerate(references, start=1):
            header = (
                f"参考题解 {index}\n"
                f"来源：{reference.source}\n"
                f"标题：{reference.title}\n"
                f"作者：{reference.author or '未知'}\n"
                f"链接：{reference.url}\n"
                "内容：\n"
            )
            budget = max_chars - used - len(header)
            if budget <= 100:
                break
            content = _trim(reference.content, min(budget, self.max_ref_chars))
            chunk = header + content
            chunks.append(chunk)
            used += len(chunk)
        return "\n\n".join(chunks)

    def _fetch_luogu(self, problem: CFProblem) -> List[SolutionReference]:
        try:
            payload = self.luogu.fetch_solution_payload(problem)
        except Exception as exc:
            LOGGER.warning("failed to fetch Luogu solutions for %s: %s", problem.cf_id, exc)
            return []
        candidates = _extract_luogu_solution_candidates(payload)
        references = []
        for candidate in candidates:
            content = _clean_reference_text(candidate.content)
            if len(content) < 80:
                continue
            content = _trim(content, self.max_ref_chars)
            references.append(
                _reference(
                    problem=problem,
                    source="luogu",
                    title=candidate.title or f"{problem.luogu_pid} 题解",
                    author=candidate.author,
                    url=candidate.url or f"https://www.luogu.com.cn/problem/solution/{problem.luogu_pid}",
                    content=content,
                )
            )
            if len(references) >= self.max_refs:
                break
        return references

    def _fetch_codeforces_editorial(self, problem: CFProblem) -> List[SolutionReference]:
        try:
            problem_html = _http_get(problem.cf_url)
        except (OSError, urllib.error.URLError, TimeoutError) as exc:
            LOGGER.warning("failed to fetch Codeforces problem page for %s: %s", problem.cf_id, exc)
            return []
        editorial_url = _find_editorial_url(problem_html)
        if not editorial_url:
            return []
        try:
            editorial_html = _http_get(editorial_url)
        except (OSError, urllib.error.URLError, TimeoutError) as exc:
            LOGGER.warning("failed to fetch Codeforces editorial for %s: %s", problem.cf_id, exc)
            return [
                _reference(
                    problem=problem,
                    source="codeforces_editorial",
                    title="Codeforces editorial link",
                    author="Codeforces",
                    url=editorial_url,
                    content=f"找到 Codeforces 题解链接：{editorial_url}",
                )
            ]
        content = _extract_readable_text(editorial_html)
        content = _trim(content, self.max_ref_chars)
        if len(content) < 80:
            content = f"找到 Codeforces 题解链接：{editorial_url}"
        return [
            _reference(
                problem=problem,
                source="codeforces_editorial",
                title="Codeforces editorial",
                author="Codeforces",
                url=editorial_url,
                content=content,
            )
        ]


class _LuoguSolutionCandidate:
    def __init__(self, title: str, author: str, url: str, content: str) -> None:
        self.title = title
        self.author = author
        self.url = url
        self.content = content


def _extract_luogu_solution_candidates(payload: Any) -> List[_LuoguSolutionCandidate]:
    candidates: List[_LuoguSolutionCandidate] = []
    seen = set()

    def visit(node: Any) -> None:
        if isinstance(node, dict):
            content = _first_text(node, ("content", "solution", "markdown", "body"))
            if content and len(content.strip()) >= 80:
                title = _first_text(node, ("title", "name")) or "洛谷题解"
                author = _extract_author(node)
                url = _extract_luogu_solution_url(node)
                key = hashlib.sha256(content.strip().encode("utf-8")).hexdigest()
                if key not in seen:
                    seen.add(key)
                    candidates.append(_LuoguSolutionCandidate(title, author, url, content))
            for value in node.values():
                visit(value)
        elif isinstance(node, list):
            for item in node:
                visit(item)

    visit(payload)
    return candidates


def _first_text(node: dict, keys: Iterable[str]) -> str:
    for key in keys:
        value = node.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _extract_author(node: dict) -> str:
    for key in ("author", "user", "poster"):
        value = node.get(key)
        if isinstance(value, str):
            return value
        if isinstance(value, dict):
            for name_key in ("name", "username", "uid"):
                name = value.get(name_key)
                if name:
                    return str(name)
    return ""


def _extract_luogu_solution_url(node: dict) -> str:
    url = node.get("url")
    if isinstance(url, str) and url.startswith("http"):
        return url
    article = node.get("article") or node.get("articleId") or node.get("article_id") or node.get("id")
    if article:
        return f"https://www.luogu.com.cn/article/{article}"
    return ""


def _find_editorial_url(problem_html: str) -> str:
    anchors = re.findall(
        r"<a[^>]+href=[\"'](?P<href>[^\"']+)[\"'][^>]*>(?P<text>.*?)</a>",
        problem_html,
        flags=re.IGNORECASE | re.DOTALL,
    )
    for href, text_html in anchors:
        text = _strip_tags(text_html).lower()
        if "tutorial" in text or "editorial" in text or "题解" in text:
            if "/blog/entry/" in href:
                return urllib.parse.urljoin("https://codeforces.com", href)
    for href, _ in anchors:
        if "/blog/entry/" in href:
            return urllib.parse.urljoin("https://codeforces.com", href)
    return ""


def _extract_readable_text(page_html: str) -> str:
    article_match = re.search(
        r"<div[^>]+class=[\"'][^\"']*ttypography[^\"']*[\"'][^>]*>(.*?)</div>\s*</div>",
        page_html,
        flags=re.IGNORECASE | re.DOTALL,
    )
    fragment = article_match.group(1) if article_match else page_html
    return _clean_reference_text(fragment)


def _clean_reference_text(text: str) -> str:
    text = re.sub(r"<script\b.*?</script>", " ", text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<style\b.*?</style>", " ", text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</p\s*>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r"\n\s*\n\s*\n+", "\n\n", text)
    return text.strip()


def _reference(problem: CFProblem, source: str, title: str, author: str, url: str, content: str) -> SolutionReference:
    return SolutionReference(
        cf_id=problem.cf_id,
        source=source,
        title=title.strip() or source,
        author=author.strip(),
        url=url.strip(),
        content=content.strip(),
        content_hash=hashlib.sha256(content.strip().encode("utf-8")).hexdigest(),
        fetched_at=datetime.now(timezone.utc).isoformat(),
    )


def _dedupe_references(references: Iterable[SolutionReference]) -> List[SolutionReference]:
    result = []
    seen = set()
    for reference in references:
        key = (reference.source, reference.content_hash)
        if key in seen:
            continue
        seen.add(key)
        result.append(reference)
    return result


def _http_get(url: str) -> str:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "qq-cf-bot/0.1",
            "Accept-Language": "en,zh-CN;q=0.9",
        },
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        return response.read().decode("utf-8", errors="replace")


def _strip_tags(fragment: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", fragment))).strip()


def _trim(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "\n\n[参考内容过长，后续内容已截断]"
