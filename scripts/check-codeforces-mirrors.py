#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import sys
import urllib.error
import urllib.request

from qq_cf_bot.cf_mirrors import codeforces_url_variants, normalize_codeforces_base_urls


def main() -> int:
    parser = argparse.ArgumentParser(description="Check Codeforces main/mirror availability for a problem page.")
    parser.add_argument("problem", help="CF id like 1A/2051F or a full Codeforces URL")
    parser.add_argument("--base-urls", default="", help="Comma-separated Codeforces base URLs")
    parser.add_argument("--timeout", type=int, default=12)
    args = parser.parse_args()

    base_urls = normalize_codeforces_base_urls(args.base_urls or None)
    url = _problem_url(args.problem)
    ok_count = 0
    for candidate in codeforces_url_variants(url, base_urls):
        try:
            html = _fetch(candidate, args.timeout)
            if _looks_like_problem_page(html):
                print(f"OK  {candidate} bytes={len(html)}")
                ok_count += 1
            else:
                print(f"BAD {candidate} reason=no problem-statement or cf-error page bytes={len(html)}")
        except Exception as exc:
            print(f"BAD {candidate} reason={exc}")
    return 0 if ok_count else 1


def _problem_url(value: str) -> str:
    if value.startswith("http://") or value.startswith("https://"):
        return value
    match = re.fullmatch(r"(\d+)([A-Za-z][A-Za-z0-9]*)", value.strip())
    if not match:
        raise SystemExit("problem must be like 1A/2051F or a full Codeforces URL")
    contest_id, index = match.groups()
    return f"https://codeforces.com/problemset/problem/{contest_id}/{index}"


def _fetch(url: str, timeout: int) -> str:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7",
            "Cache-Control": "no-cache",
            "Referer": url,
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"HTTP {exc.code}") from exc


def _looks_like_problem_page(html: str) -> bool:
    lowered = html.lower()
    return "problem-statement" in lowered and "cf-error" not in lowered and "captcha" not in lowered


if __name__ == "__main__":
    sys.exit(main())
