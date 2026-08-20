from __future__ import annotations

import hashlib
import html
import re
from pathlib import Path
from typing import Iterable, List
from urllib.parse import urlsplit

from .models import CFProblem, ProblemStatement


_RELATIVE_SRC_RE = re.compile(r"""(?P<prefix>\s(?:src|href)=["'])(?P<url>/[^"']+)(?P<suffix>["'])""")
_MATH_RE = re.compile(r"(?<!\\)(\${1,3})(.+?)(?<!\\)\1", re.DOTALL)
_LEFTOVER_MATH_RE = re.compile(r"(\${2,3})([^$<>]+?)\1", re.DOTALL)


class StatementRenderer:
    def __init__(
        self,
        asset_dir: Path,
        width: int = 760,
        viewport_height: int = 1100,
        max_slice_height: int = 2400,
    ) -> None:
        self.asset_dir = asset_dir
        self.width = width
        self.viewport_height = viewport_height
        self.max_slice_height = max_slice_height
        self.asset_dir.mkdir(parents=True, exist_ok=True)

    def render(self, problem: CFProblem, statement: ProblemStatement, reveal_metadata: bool = True) -> List[Path]:
        try:
            from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise RuntimeError(
                "playwright is required for image rendering. Run: pip install -r requirements.txt && playwright install chromium"
            ) from exc

        cards = self._build_cards(problem, statement, reveal_metadata)
        if not cards:
            raise RuntimeError("no renderable statement cards were produced")

        paths: List[Path] = []
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            try:
                context = browser.new_context(
                    viewport={"width": self.width, "height": self.viewport_height},
                    device_scale_factor=2,
                    locale="zh-CN",
                )
                page = context.new_page()
                for index, card_html in enumerate(cards):
                    page.set_content(self._wrap_page(card_html), wait_until="domcontentloaded", timeout=20_000)
                    try:
                        page.wait_for_load_state("networkidle", timeout=10_000)
                    except PlaywrightTimeoutError:
                        pass
                    try:
                        page.evaluate("document.fonts && document.fonts.ready")
                    except Exception:
                        pass
                    page.wait_for_timeout(300)
                    paths.extend(self._screenshot_card(page, problem, index))
            finally:
                browser.close()
        return paths

    def _screenshot_card(self, page, problem: CFProblem, index: int) -> List[Path]:
        card = page.locator("#card")
        box = card.bounding_box()
        if box is None:
            raise RuntimeError("rendered card is not visible")

        base = f"{problem.cf_id}-{index}-{_short_hash(problem.cf_id + str(index))}"
        if box["height"] <= self.max_slice_height:
            path = self.asset_dir / f"{base}.png"
            card.screenshot(path=str(path))
            return [path]

        paths = []
        height = int(box["height"])
        part = 0
        for y in range(0, height, self.max_slice_height):
            path = self.asset_dir / f"{base}-{part}.png"
            page.screenshot(
                path=str(path),
                clip={
                    "x": box["x"],
                    "y": box["y"] + y,
                    "width": box["width"],
                    "height": min(self.max_slice_height, height - y),
                },
            )
            paths.append(path)
            part += 1
        return paths

    def _build_cards(self, problem: CFProblem, statement: ProblemStatement, reveal_metadata: bool = True) -> List[str]:
        overview_parts = []
        if reveal_metadata:
            meta = [
                f"Codeforces {html.escape(problem.cf_id)}",
                f"Rating {problem.rating}",
            ]
            if problem.tags:
                meta.append("Tags " + ", ".join(html.escape(tag) for tag in problem.tags[:8]))
            overview_parts.extend(
                [
                    f"<h1>{html.escape(statement.title or problem.name)}</h1>",
                    f"<div class=\"meta\">{' / '.join(meta)}</div>",
                ]
            )
        overview_parts.extend(self._markdown_section("题目描述", statement.description, statement.source_url))
        overview_parts.extend(self._markdown_section("输入", statement.input_format, statement.source_url))
        overview_parts.extend(self._markdown_section("输出", statement.output_format, statement.source_url))

        sample_parts = []
        for idx, (sample_input, sample_output) in enumerate(statement.samples, start=1):
            sample_parts.append(f"<h2>样例 #{idx}</h2>")
            sample_parts.append("<h3>输入</h3>")
            sample_parts.append(f"<pre>{html.escape(sample_input.rstrip())}</pre>")
            sample_parts.append("<h3>输出</h3>")
            sample_parts.append(f"<pre>{html.escape(sample_output.rstrip())}</pre>")
        sample_parts.extend(self._markdown_section("注释", statement.hint, statement.source_url))

        footer = ""
        if reveal_metadata:
            footer = (
                "<div class=\"footer\">"
                f"<span>{html.escape(problem.cf_url)}</span>"
                f"<span>{html.escape(problem.luogu_url)}</span>"
                "</div>"
            )

        cards = []
        if overview_parts:
            cards.append("<article id=\"card\" class=\"card\">" + "".join(overview_parts) + footer + "</article>")
        if sample_parts:
            cards.append("<article id=\"card\" class=\"card\">" + "".join(sample_parts) + footer + "</article>")
        return cards

    def _markdown_section(self, title: str, markdown_text: str, source_url: str = "") -> List[str]:
        if not markdown_text.strip():
            return []
        return [
            f"<h2>{html.escape(title)}</h2>",
            f"<div class=\"markdown\">{_markdown_to_html(markdown_text, source_url)}</div>",
        ]

    def _wrap_page(self, card_html: str) -> str:
        return f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
* {{ box-sizing: border-box; }}
html, body {{ margin: 0; padding: 0; background: #111; }}
body {{
  width: {self.width}px;
  color: #1f2933;
  font-family: -apple-system, BlinkMacSystemFont, "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", Arial, sans-serif;
  line-height: 1.7;
}}
.card {{
  width: {self.width - 40}px;
  margin: 20px;
  padding: 30px 34px 28px;
  background: #fff;
  overflow: hidden;
}}
h1 {{
  margin: 0 0 10px;
  font-size: 28px;
  line-height: 1.25;
  font-weight: 750;
  letter-spacing: 0;
}}
.meta {{
  margin: 0 0 24px;
  color: #687383;
  font-size: 14px;
  line-height: 1.45;
}}
h2 {{
  margin: 24px 0 10px;
  font-size: 22px;
  line-height: 1.35;
  font-weight: 750;
}}
h3 {{
  margin: 16px 0 8px;
  font-size: 17px;
  line-height: 1.35;
  font-weight: 700;
}}
p {{ margin: 10px 0 14px; font-size: 20px; }}
ul, ol {{ margin: 10px 0 14px 26px; padding: 0; font-size: 20px; }}
li {{ margin: 4px 0; }}
code {{
  padding: 1px 5px;
  border-radius: 4px;
  background: #eef0f3;
  font-family: Menlo, Consolas, "SFMono-Regular", monospace;
  font-size: 0.88em;
}}
.math {{
  display: inline;
  padding: 0 1px;
  color: #111827;
  font-family: "Times New Roman", "STIX Two Math", "Cambria Math", serif;
  font-size: 1.02em;
  overflow-wrap: anywhere;
}}
.math-display {{
  display: block;
  margin: 8px auto 14px;
  text-align: center;
  font-size: 1.08em;
  line-height: 1.55;
}}
.math code {{
  padding: 0 3px;
  background: #eef0f3;
  font-family: Menlo, Consolas, "SFMono-Regular", monospace;
  font-size: 0.92em;
}}
pre {{
  width: 100%;
  margin: 8px 0 16px;
  padding: 16px 18px;
  border-radius: 3px;
  background: #d8dae1;
  color: #4a5568;
  overflow: hidden;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  font-family: Menlo, Consolas, "SFMono-Regular", monospace;
  font-size: 18px;
  line-height: 1.45;
}}
pre code {{ padding: 0; background: transparent; font-size: inherit; }}
blockquote {{
  margin: 14px 0;
  padding: 8px 14px;
  border-left: 4px solid #cbd5e1;
  background: #f7f8fa;
}}
table {{
  width: 100%;
  border-collapse: collapse;
  margin: 12px 0 16px;
  font-size: 17px;
}}
td, th {{
  border: 1px solid #d7dbe3;
  padding: 8px 10px;
  text-align: left;
}}
img {{
  display: block;
  max-width: 100%;
  height: auto;
  margin: 12px auto;
}}
.footer {{
  display: flex;
  flex-direction: column;
  gap: 3px;
  margin-top: 26px;
  padding-top: 14px;
  border-top: 1px solid #e5e7eb;
  color: #7a8493;
  font-size: 13px;
  line-height: 1.45;
  overflow-wrap: anywhere;
}}
</style>
</head>
<body>{card_html}</body>
</html>"""


def _markdown_to_html(markdown_text: str, source_url: str = "") -> str:
    try:
        import markdown
    except ImportError as exc:
        raise RuntimeError("markdown is required for Luogu markdown rendering. Run: pip install -r requirements.txt") from exc

    markdown_text = _normalize_statement_markup(markdown_text)
    markdown_text, math_fragments = _stash_math(markdown_text)
    rendered = markdown.markdown(
        markdown_text,
        extensions=["extra", "sane_lists", "nl2br"],
        output_format="html5",
    )
    for token, fragment in math_fragments.items():
        rendered = rendered.replace(token, fragment)
    rendered = _render_leftover_math(rendered)
    rendered = _render_loose_math_tokens(rendered)
    base_url = _origin(source_url) or "https://www.luogu.com.cn"
    return _RELATIVE_SRC_RE.sub(lambda match: _absolute_attr(match, base_url), rendered)


def _stash_math(value: str) -> tuple[str, dict[str, str]]:
    fragments: dict[str, str] = {}

    def replace(match: re.Match) -> str:
        content = match.group(2).strip()
        if not content:
            return ""
        token = f"QQCFBOTMATH{len(fragments)}TOKEN"
        display = _is_line_standalone_math(match)
        fragments[token] = _latex_to_html(content, display=display)
        if display:
            return f"\n\n{token}\n\n"
        return token

    return _MATH_RE.sub(replace, value), fragments


def _latex_to_html(value: str, display: bool = False) -> str:
    text = html.unescape(value).replace("\n", " ")
    code_fragments: dict[str, str] = {}

    def stash_code(match: re.Match) -> str:
        token = f"QQCFBOTCODE{len(code_fragments)}TOKEN"
        code_fragments[token] = f"<code>{html.escape(match.group(1))}</code>"
        return token

    text = re.sub(r"\\texttt\{([^{}]*)\}", stash_code, text)
    text = re.sub(r"\\(?:text|mathrm|operatorname)\{([^{}]*)\}", r"\1", text)
    text = _normalize_formula_text(text)
    replacements = {
        r"\leq": "≤",
        r"\le": "≤",
        r"\geq": "≥",
        r"\ge": "≥",
        r"\neq": "≠",
        r"\ne": "≠",
        r"\lt": "<",
        r"\gt": ">",
        r"\mid": "∣",
        r"\nmid": "∤",
        r"\cdot": "·",
        r"\times": "×",
        r"\ldots": "…",
        r"\dots": "…",
        r"\in": "∈",
        r"\notin": "∉",
        r"\sum": "∑",
        r"\min": "min",
        r"\max": "max",
        r"\left": "",
        r"\right": "",
        r"\lfloor": "⌊",
        r"\rfloor": "⌋",
        r"\lceil": "⌈",
        r"\rceil": "⌉",
    }
    for source, target in replacements.items():
        text = text.replace(source, target)
    text = re.sub(r"\\([A-Za-z]+)", r"\1", text)
    text = _compact_math_spacing(text)
    text = re.sub(r"\s+", " ", text).strip()
    escaped = _format_math_markup(text)
    for token, fragment in code_fragments.items():
        escaped = escaped.replace(token, fragment)
    css_class = "math math-display" if display else "math"
    return f'<span class="{css_class}">{escaped}</span>'


def _is_line_standalone_math(match: re.Match) -> bool:
    source = match.string
    start, end = match.span()
    line_start = source.rfind("\n", 0, start) + 1
    line_end = source.find("\n", end)
    if line_end == -1:
        line_end = len(source)
    line = source[line_start:line_end].strip()
    return line == match.group(0).strip()


def normalize_statement_markup(value: str) -> str:
    text = html.unescape(value)
    text = text.replace("＄", "$")
    text = re.sub(r"\\(?=\${1,3})", "", text)
    text = text.replace(r"\_", "_")
    text = _repair_corrupted_latex(text)
    text = _normalize_plain_latex_commands(text)
    text = _compact_math_spacing(text)
    return text


def _normalize_statement_markup(value: str) -> str:
    return normalize_statement_markup(value)


def _render_leftover_math(value: str) -> str:
    def replace(match: re.Match) -> str:
        content = match.group(2).strip()
        if not content:
            return ""
        return _latex_to_html(content)

    return _LEFTOVER_MATH_RE.sub(replace, value)


def _render_loose_math_tokens(value: str) -> str:
    chunks = re.split(
        r"(<(?:pre|code)\b[^>]*>.*?</(?:pre|code)>|<span class=\"math\">.*?</span>|<[^>]+>)",
        value,
        flags=re.DOTALL | re.IGNORECASE,
    )
    for index, chunk in enumerate(chunks):
        if not chunk or chunk.startswith("<"):
            continue
        chunks[index] = _format_loose_math_text(chunk)
    return "".join(chunks)


def _format_loose_math_text(value: str) -> str:
    text = re.sub(r"\${1,3}", "", value)
    protected: dict[str, str] = {}

    def protect_raw(fragment: str) -> str:
        token = f"QQCFBOTLOOSEMATH{len(protected)}TOKEN"
        protected[token] = f'<span class="math">{html.escape(fragment)}</span>'
        return token

    def protect_latex(match: re.Match) -> str:
        token = f"QQCFBOTLOOSEMATH{len(protected)}TOKEN"
        protected[token] = _latex_to_html(match.group(1))
        return token

    script = r"(?:_\{(?:[^{}]|\{[^{}]*\}){1,120}\}|_[A-Za-z0-9]+|\^\{(?:[^{}]|\{[^{}]*\}){1,120}\}|\^[A-Za-z0-9]+)"
    scripted_term = rf"[A-Za-z∑Σ]\s*(?:{script})+"
    math_term = rf"(?:{scripted_term}|[A-Za-z∑Σ0-9]+)"
    text = re.sub(r"([⌊⌈][^⌊⌋⌈⌉<>]{1,60}[⌋⌉])", lambda match: protect_raw(match.group(1)), text)
    text = re.sub(
        r"(?<![A-Za-z0-9])"
        rf"({scripted_term}(?:\s*[=+\-*/<>≤≥∣]\s*{math_term})+)"
        r"(?![A-Za-z0-9])",
        protect_latex,
        text,
    )
    text = re.sub(
        r"(?<![A-Za-z0-9])"
        rf"({scripted_term})"
        r"(?![A-Za-z0-9])",
        protect_latex,
        text,
    )
    text = re.sub(
        r"(?<![A-Za-z0-9])([A-Za-z])_([A-Za-z0-9]+)(?![A-Za-z0-9])",
        lambda match: f'<span class="math">{html.escape(match.group(1))}<sub>{html.escape(match.group(2))}</sub></span>',
        text,
    )
    text = re.sub(
        r"(?<![A-Za-z0-9])(\d+)\^([A-Za-z0-9+-]+)(?![A-Za-z0-9])",
        lambda match: f'<span class="math">{html.escape(match.group(1))}<sup>{html.escape(match.group(2))}</sup></span>',
        text,
    )
    for token, fragment in protected.items():
        text = text.replace(token, fragment)
    return text


def _repair_corrupted_latex(value: str) -> str:
    text = value
    text = re.sub(
        r"([∑Σ])_([A-Za-z])=([A-Za-z0-9+\-]+)\^([A-Za-z0-9+\-]+)",
        lambda match: rf"\sum_{{{match.group(2)}={match.group(3)}}}^{{{match.group(4)}}}",
        text,
    )
    text = re.sub(
        r"([∑Σ])\s*([A-Za-z])\s*=\s*([A-Za-z0-9+\-]+)\s*\^\s*([A-Za-z0-9+\-]+)",
        lambda match: rf"\sum_{{{match.group(2)}={match.group(3)}}}^{{{match.group(4)}}}",
        text,
    )
    text = re.sub(
        r"[<≤]?ftl(floor|ceil)d?frac([A-Za-z](?:_[A-Za-z0-9]+)?)2r(floor|ceil)",
        lambda match: _floor_ceil_text(match.group(1), f"{match.group(2)}/2", match.group(3)),
        text,
    )
    text = re.sub(
        r"[<≤]?ftl(floor|ceil)d?frac\{([^{}]+)\}\{([^{}]+)\}r(floor|ceil)",
        lambda match: _floor_ceil_text(match.group(1), f"{match.group(2)}/{match.group(3)}", match.group(4)),
        text,
    )
    text = re.sub(
        r"(?<![A-Za-z])(?:d?frac)([A-Za-z](?:_[A-Za-z0-9]+)?)(\d+)(?![A-Za-z])",
        r"\1/\2",
        text,
    )
    return text


def _floor_ceil_text(open_name: str, inner: str, close_name: str) -> str:
    open_symbol = "⌊" if open_name == "floor" else "⌈"
    close_symbol = "⌋" if close_name == "floor" else "⌉"
    normalized_inner = inner.replace("{", "").replace("}", "")
    if "/" not in normalized_inner and normalized_inner.endswith("2"):
        normalized_inner = normalized_inner[:-1] + "/2"
    return f"{open_symbol}{normalized_inner}{close_symbol}"


def _normalize_plain_latex_commands(value: str) -> str:
    text = value
    replacements = {
        "ldots": "…",
        "dots": "…",
        "cdot": "·",
        "times": "×",
    }
    for source, target in replacements.items():
        text = re.sub(rf"(?<![A-Za-z\\]){source}(?![A-Za-z])", target, text)
    math_atom = r"([A-Za-z∑Σ0-9_^{}\[\]()+\-]+)"
    text = re.sub(rf"(?<![A-Za-z]){math_atom}\s+mid\s+{math_atom}(?![A-Za-z])", r"\1 ∣ \2", text)
    text = re.sub(rf"(?<![A-Za-z]){math_atom}\s+nmid\s+{math_atom}(?![A-Za-z])", r"\1 ∤ \2", text)
    text = re.sub(rf"(?<![A-Za-z]){math_atom}\s+lt\s+{math_atom}(?![A-Za-z])", r"\1 < \2", text)
    text = re.sub(rf"(?<![A-Za-z]){math_atom}\s+gt\s+{math_atom}(?![A-Za-z])", r"\1 > \2", text)
    text = re.sub(r"(?<![A-Za-z\\])leq?(?![A-Za-z])", "≤", text)
    text = re.sub(r"(?<![A-Za-z\\])geq?(?![A-Za-z])", "≥", text)
    text = re.sub(r"(?<![A-Za-z\\])neq?(?![A-Za-z])", "≠", text)
    return text


def _normalize_formula_text(value: str) -> str:
    text = value
    for _ in range(4):
        next_text = re.sub(r"\\(?:dfrac|frac)\{([^{}]+)\}\{([^{}]+)\}", r"\1/\2", text)
        if next_text == text:
            break
        text = next_text
    text = re.sub(r"\\?lfloor\s*([^⌊⌋]+?)\s*\\?rfloor", r"⌊\1⌋", text)
    text = re.sub(r"\\?lceil\s*([^⌈⌉]+?)\s*\\?rceil", r"⌈\1⌉", text)
    text = _repair_corrupted_latex(text)
    text = _normalize_plain_latex_commands(text)
    return text


def _compact_math_spacing(value: str) -> str:
    text = value
    text = re.sub(r"([A-Za-z])_\s+([A-Za-z0-9])", r"\1_\2", text)
    text = re.sub(r"(\d+)\s*\^\s*([A-Za-z0-9+-]+)", r"\1^\2", text)
    text = re.sub(r"([A-Za-z])\s*\^\s*([A-Za-z0-9+-]+)", r"\1^\2", text)
    text = re.sub(r"\s+([,.;:，。；：、）\]\}])", r"\1", text)
    return text


def _format_math_markup(value: str) -> str:
    text = value.replace(r"\{", "{").replace(r"\}", "}")
    text = text.replace("<=", "≤").replace(">=", "≥").replace("!=", "≠")
    rendered, _ = _format_math_sequence(text, 0, "")
    return rendered


def _format_math_sequence(value: str, index: int = 0, stop: str = "") -> tuple[str, int]:
    parts: List[str] = []
    while index < len(value):
        char = value[index]
        if stop and char == stop:
            return "".join(parts), index + 1
        if char in "_^":
            tag = "sub" if char == "_" else "sup"
            inner, index = _consume_math_script(value, index + 1)
            if inner:
                parts.append(f"<{tag}>{inner}</{tag}>")
            continue
        if char == "{":
            inner, index = _format_math_sequence(value, index + 1, "}")
            parts.append(inner)
            continue
        if char == "}":
            return "".join(parts), index + 1
        if char == "\\":
            command, next_index = _consume_latex_command(value, index)
            if command:
                parts.append(html.escape(_latex_command_text(command)))
                index = next_index
                continue
        parts.append(html.escape(char))
        index += 1
    return "".join(parts), index


def _consume_math_script(value: str, index: int) -> tuple[str, int]:
    while index < len(value) and value[index].isspace():
        index += 1
    if index >= len(value):
        return "", index
    if value[index] == "{":
        return _format_math_sequence(value, index + 1, "}")
    if value[index] == "\\":
        command, next_index = _consume_latex_command(value, index)
        if command:
            return html.escape(_latex_command_text(command)), next_index

    start = index
    if value[index].isalnum():
        while index < len(value) and value[index].isalnum():
            index += 1
    else:
        index += 1
    return html.escape(value[start:index]), index


def _consume_latex_command(value: str, index: int) -> tuple[str, int]:
    match = re.match(r"\\[A-Za-z]+", value[index:])
    if not match:
        return "", index
    command = match.group(0)
    return command, index + len(command)


def _latex_command_text(command: str) -> str:
    replacements = {
        r"\leq": "≤",
        r"\le": "≤",
        r"\geq": "≥",
        r"\ge": "≥",
        r"\neq": "≠",
        r"\ne": "≠",
        r"\lt": "<",
        r"\gt": ">",
        r"\mid": "∣",
        r"\nmid": "∤",
        r"\cdot": "·",
        r"\times": "×",
        r"\ldots": "…",
        r"\dots": "…",
        r"\in": "∈",
        r"\notin": "∉",
        r"\sum": "∑",
        r"\min": "min",
        r"\max": "max",
        r"\left": "",
        r"\right": "",
        r"\lfloor": "⌊",
        r"\rfloor": "⌋",
        r"\lceil": "⌈",
        r"\rceil": "⌉",
    }
    return replacements.get(command, command.lstrip("\\"))


def _origin(url: str) -> str:
    parsed = urlsplit(url)
    if not parsed.scheme or not parsed.netloc:
        return ""
    return f"{parsed.scheme}://{parsed.netloc}"


def _absolute_attr(match: re.Match, base_url: str) -> str:
    return f"{match.group('prefix')}{base_url}{match.group('url')}{match.group('suffix')}"


def _short_hash(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:8]
