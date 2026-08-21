from __future__ import annotations

import urllib.parse
from typing import Iterable, Tuple


DEFAULT_CODEFORCES_BASE_URLS = (
    "https://codeforces.com",
    "https://m1.codeforces.com",
    "https://m2.codeforces.com",
    "https://m3.codeforces.com",
)


def normalize_codeforces_base_urls(base_urls: Iterable[str] | str | None = None) -> Tuple[str, ...]:
    if base_urls is None:
        raw_items: Iterable[str] = DEFAULT_CODEFORCES_BASE_URLS
    elif isinstance(base_urls, str):
        raw_items = base_urls.replace(";", ",").split(",")
    else:
        raw_items = base_urls

    normalized = []
    seen = set()
    for item in raw_items:
        base = str(item).strip().rstrip("/")
        if not base:
            continue
        if "://" not in base:
            base = "https://" + base
        parsed = urllib.parse.urlsplit(base)
        if not parsed.scheme or not parsed.netloc:
            continue
        cleaned = urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, "", "", ""))
        if cleaned not in seen:
            seen.add(cleaned)
            normalized.append(cleaned)
    return tuple(normalized) or DEFAULT_CODEFORCES_BASE_URLS


def codeforces_url_variants(url: str, base_urls: Iterable[str] | str | None = None) -> Tuple[str, ...]:
    bases = normalize_codeforces_base_urls(base_urls)
    parsed = urllib.parse.urlsplit(url)
    if not parsed.netloc:
        path = url if url.startswith("/") else "/" + url
        return _dedupe(urllib.parse.urljoin(base + "/", path.lstrip("/")) for base in bases)

    host = parsed.netloc.lower()
    if host == "codeforces.com" or host.endswith(".codeforces.com"):
        variants = []
        paths = _problem_page_paths(parsed.path)
        for base in bases:
            base_parsed = urllib.parse.urlsplit(base)
            for path in paths:
                variants.append(
                    urllib.parse.urlunsplit(
                        (base_parsed.scheme, base_parsed.netloc, path, parsed.query, parsed.fragment)
                    )
                )
        return _dedupe(variants)

    return (url,)


def _problem_page_paths(path: str) -> Tuple[str, ...]:
    normalized = path.rstrip("/") or "/"
    problemset_prefix = "/problemset/problem/"
    contest_marker = "/problem/"
    if normalized.startswith(problemset_prefix):
        parts = normalized[len(problemset_prefix) :].split("/", 1)
        if len(parts) == 2 and parts[0] and parts[1]:
            return (path, f"/contest/{parts[0]}/problem/{parts[1]}")

    if normalized.startswith("/contest/") and contest_marker in normalized:
        prefix, index = normalized.rsplit(contest_marker, 1)
        contest_id = prefix[len("/contest/") :]
        if contest_id and index:
            return (path, f"/problemset/problem/{contest_id}/{index}")

    return (path,)


def _dedupe(items: Iterable[str]) -> Tuple[str, ...]:
    result = []
    seen = set()
    for item in items:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return tuple(result)
