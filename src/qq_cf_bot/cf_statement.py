from __future__ import annotations

import re
import urllib.error
import urllib.request
from html import unescape
from html.parser import HTMLParser
from typing import Dict, Iterable, List, Optional, Tuple

from .models import CFProblem, ProblemStatement


class CodeforcesStatementClient:
    def fetch_statement(self, problem: CFProblem) -> ProblemStatement:
        html = fetch_codeforces_html(problem.cf_url, validate=_looks_like_problem_page)
        return statement_from_codeforces_html(problem, html)


def fetch_codeforces_html(url: str, validate=None, timeout_seconds: int = 25) -> str:
    last_error: Optional[Exception] = None
    try:
        html = _fetch_http(url, timeout_seconds)
        if validate is None or validate(html):
            return html
        last_error = RuntimeError("Codeforces returned HTML that did not pass validation")
    except Exception as exc:
        last_error = exc

    try:
        html = _fetch_playwright(url)
        if validate is None or validate(html):
            return html
        raise RuntimeError("Codeforces Playwright fallback returned invalid HTML")
    except Exception as exc:
        if last_error is not None:
            raise RuntimeError(f"Codeforces fetch failed for {url}: {last_error}; fallback failed: {exc}") from exc
        raise


def _fetch_http(url: str, timeout_seconds: int) -> str:
    request = urllib.request.Request(url, headers=_browser_headers(url))
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            return response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"Codeforces returned HTTP {exc.code} for {url}") from exc


def _fetch_playwright(url: str) -> str:
    try:
        from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RuntimeError("playwright is required for Codeforces fetch fallback") from exc

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent=_browser_headers(url)["User-Agent"],
            locale="en-US",
            extra_http_headers={
                key: value
                for key, value in _browser_headers(url).items()
                if key.lower() != "user-agent"
            },
        )
        try:
            page = context.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=30_000)
            try:
                page.wait_for_load_state("networkidle", timeout=8_000)
            except PlaywrightTimeoutError:
                pass
            return page.content()
        finally:
            context.close()
            browser.close()


def statement_from_codeforces_html(problem: CFProblem, html: str) -> ProblemStatement:
    root = _DOMParser().parse(html)
    statement = root.find_first_by_class("problem-statement")
    if statement is None:
        raise RuntimeError(f"Codeforces page for {problem.cf_id} does not contain problem-statement")

    header = statement.find_first_by_class("header")
    title = _text(header.find_first_by_class("title")) if header else ""
    description_nodes = []
    input_node = None
    output_node = None
    sample_node = None
    note_node = None

    for child in statement.children:
        if child.tag != "div":
            continue
        classes = child.class_names
        if "header" in classes:
            continue
        if "input-specification" in classes:
            input_node = child
        elif "output-specification" in classes:
            output_node = child
        elif "sample-tests" in classes:
            sample_node = child
        elif "note" in classes:
            note_node = child
        elif not classes:
            description_nodes.append(child)

    return ProblemStatement(
        pid=problem.cf_id,
        title=_normalize_text(title) or problem.name,
        description=_join_html(description_nodes),
        input_format=_section_html(input_node),
        output_format=_section_html(output_node),
        samples=list(_samples(sample_node)),
        hint=_section_html(note_node),
        source_url=problem.cf_url,
    )


def _browser_headers(referer: str) -> Dict[str, str]:
    return {
        "User-Agent": (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7",
        "Cache-Control": "no-cache",
        "Referer": referer,
    }


def _looks_like_problem_page(html: str) -> bool:
    lowered = html.lower()
    return "problem-statement" in lowered and "cf-error" not in lowered and "captcha" not in lowered


def _section_html(node: Optional["_Node"]) -> str:
    if node is None:
        return ""
    parts = []
    for child in node.children:
        if "section-title" in child.class_names:
            continue
        parts.append(child.to_html())
    return _clean_html("".join(parts))


def _join_html(nodes: Iterable["_Node"]) -> str:
    return _clean_html("".join(node.to_html() for node in nodes))


def _samples(node: Optional["_Node"]) -> Iterable[Tuple[str, str]]:
    if node is None:
        return
    sample_tests = [child for child in node.children if "sample-test" in child.class_names]
    if not sample_tests:
        sample_tests = [node]

    for sample in sample_tests:
        inputs = sample.find_all_by_class("input")
        outputs = sample.find_all_by_class("output")
        for input_node, output_node in zip(inputs, outputs):
            yield _pre_text(input_node), _pre_text(output_node)


def _pre_text(node: "_Node") -> str:
    pre = node.find_first("pre")
    if pre is None:
        return ""
    return _normalize_pre(_text(pre))


def _clean_html(value: str) -> str:
    value = re.sub(r"<div[^>]*class=[\"']section-title[\"'][^>]*>.*?</div>", "", value, flags=re.DOTALL)
    value = re.sub(r"\s+", " ", value)
    value = re.sub(r">\s+<", "><", value)
    return value.strip()


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", unescape(value)).strip()


def _normalize_pre(value: str) -> str:
    lines = unescape(value).replace("\xa0", " ").splitlines()
    return "\n".join(line.rstrip() for line in lines).strip("\n")


def _text(node: Optional["_Node"]) -> str:
    if node is None:
        return ""
    return node.text()


class _Node:
    def __init__(self, tag: str = "", attrs: Optional[Dict[str, str]] = None, text: str = "") -> None:
        self.tag = tag
        self.attrs = attrs or {}
        self.raw_text = text
        self.children: List[_Node] = []

    @property
    def class_names(self) -> set[str]:
        return set((self.attrs.get("class") or "").split())

    def find_first(self, tag: str) -> Optional["_Node"]:
        if self.tag == tag:
            return self
        for child in self.children:
            found = child.find_first(tag)
            if found is not None:
                return found
        return None

    def find_first_by_class(self, class_name: str) -> Optional["_Node"]:
        if class_name in self.class_names:
            return self
        for child in self.children:
            found = child.find_first_by_class(class_name)
            if found is not None:
                return found
        return None

    def find_all_by_class(self, class_name: str) -> List["_Node"]:
        found = [self] if class_name in self.class_names else []
        for child in self.children:
            found.extend(child.find_all_by_class(class_name))
        return found

    def text(self) -> str:
        if self.tag == "#text":
            return self.raw_text
        if self.tag == "br":
            return "\n"
        return "".join(child.text() for child in self.children)

    def to_html(self) -> str:
        if self.tag == "#text":
            return self.raw_text
        attrs = "".join(
            f' {name}="{_escape_attr(value)}"'
            for name, value in self.attrs.items()
            if name in {"class", "href", "src", "alt", "title"}
        )
        inner = "".join(child.to_html() for child in self.children)
        if self.tag in {"br", "img"}:
            return f"<{self.tag}{attrs}>"
        return f"<{self.tag}{attrs}>{inner}</{self.tag}>"


class _DOMParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=False)
        self.root = _Node("document")
        self.stack = [self.root]

    def parse(self, html: str) -> _Node:
        self.feed(html)
        self.close()
        return self.root

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]) -> None:
        node = _Node(tag, {name: value or "" for name, value in attrs})
        self.stack[-1].children.append(node)
        if tag not in {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source"}:
            self.stack.append(node)

    def handle_startendtag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]) -> None:
        self.stack[-1].children.append(_Node(tag, {name: value or "" for name, value in attrs}))

    def handle_endtag(self, tag: str) -> None:
        for index in range(len(self.stack) - 1, 0, -1):
            if self.stack[index].tag == tag:
                del self.stack[index:]
                return

    def handle_data(self, data: str) -> None:
        if data:
            self.stack[-1].children.append(_Node("#text", text=data))

    def handle_entityref(self, name: str) -> None:
        self.handle_data(f"&{name};")

    def handle_charref(self, name: str) -> None:
        self.handle_data(f"&#{name};")


def _escape_attr(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace('"', "&quot;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
