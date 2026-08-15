from __future__ import annotations

import hashlib
import html
import re
from pathlib import Path
from typing import Iterable, List

from .models import CFProblem, ProblemStatement


_RELATIVE_SRC_RE = re.compile(r"""(?P<prefix>\s(?:src|href)=["'])(?P<url>/[^"']+)(?P<suffix>["'])""")


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

    def render(self, problem: CFProblem, statement: ProblemStatement) -> List[Path]:
        try:
            from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise RuntimeError(
                "playwright is required for image rendering. Run: pip install -r requirements.txt && playwright install chromium"
            ) from exc

        cards = self._build_cards(problem, statement)
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

    def _build_cards(self, problem: CFProblem, statement: ProblemStatement) -> List[str]:
        meta = [
            f"Codeforces {html.escape(problem.cf_id)}",
            f"Rating {problem.rating}",
        ]
        if problem.tags:
            meta.append("Tags " + ", ".join(html.escape(tag) for tag in problem.tags[:8]))

        overview_parts = [
            f"<h1>{html.escape(statement.title or problem.name)}</h1>",
            f"<div class=\"meta\">{' / '.join(meta)}</div>",
        ]
        overview_parts.extend(self._markdown_section("题目描述", statement.description))
        overview_parts.extend(self._markdown_section("输入", statement.input_format))
        overview_parts.extend(self._markdown_section("输出", statement.output_format))

        sample_parts = []
        for idx, (sample_input, sample_output) in enumerate(statement.samples, start=1):
            sample_parts.append(f"<h2>样例 #{idx}</h2>")
            sample_parts.append("<h3>输入</h3>")
            sample_parts.append(f"<pre>{html.escape(sample_input.rstrip())}</pre>")
            sample_parts.append("<h3>输出</h3>")
            sample_parts.append(f"<pre>{html.escape(sample_output.rstrip())}</pre>")
        sample_parts.extend(self._markdown_section("注释", statement.hint))

        footer = (
            "<div class=\"footer\">"
            f"<span>{html.escape(problem.cf_url)}</span>"
            f"<span>{html.escape(problem.luogu_url)}</span>"
            "</div>"
        )

        cards = []
        if len(overview_parts) > 2:
            cards.append("<article id=\"card\" class=\"card\">" + "".join(overview_parts) + footer + "</article>")
        if sample_parts:
            cards.append("<article id=\"card\" class=\"card\">" + "".join(sample_parts) + footer + "</article>")
        return cards

    def _markdown_section(self, title: str, markdown_text: str) -> List[str]:
        if not markdown_text.strip():
            return []
        return [
            f"<h2>{html.escape(title)}</h2>",
            f"<div class=\"markdown\">{_markdown_to_html(markdown_text)}</div>",
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


def _markdown_to_html(markdown_text: str) -> str:
    try:
        import markdown
    except ImportError as exc:
        raise RuntimeError("markdown is required for Luogu markdown rendering. Run: pip install -r requirements.txt") from exc

    rendered = markdown.markdown(
        markdown_text,
        extensions=["extra", "sane_lists", "nl2br"],
        output_format="html5",
    )
    return _RELATIVE_SRC_RE.sub(
        lambda match: f"{match.group('prefix')}https://www.luogu.com.cn{match.group('url')}{match.group('suffix')}",
        rendered,
    )


def _short_hash(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:8]
