from __future__ import annotations

import hashlib
import html
from pathlib import Path
from typing import List, Sequence

from .models import UserStat
from .rating import leaderboard_rating


class RanklistRenderer:
    def __init__(self, asset_dir: Path, width: int = 760, viewport_height: int = 1200) -> None:
        self.asset_dir = asset_dir
        self.width = width
        self.viewport_height = viewport_height
        self.asset_dir.mkdir(parents=True, exist_ok=True)

    def render(self, group_id: int, stats: Sequence[UserStat]) -> Path:
        try:
            from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise RuntimeError(
                "playwright is required for ranklist rendering. Run: pip install -r requirements.txt && playwright install chromium"
            ) from exc

        html_doc = self._wrap_page(group_id, stats)
        path = self.asset_dir / f"ranklist-{group_id}-{_stats_hash(stats)}.png"
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            try:
                page = browser.new_page(
                    viewport={"width": self.width, "height": self.viewport_height},
                    device_scale_factor=2,
                    locale="zh-CN",
                )
                page.set_content(html_doc, wait_until="domcontentloaded", timeout=20_000)
                try:
                    page.wait_for_load_state("networkidle", timeout=10_000)
                except PlaywrightTimeoutError:
                    pass
                page.wait_for_timeout(300)
                page.locator("#rank-card").screenshot(path=str(path))
            finally:
                browser.close()
        return path

    def _wrap_page(self, group_id: int, stats: Sequence[UserStat]) -> str:
        rows = "\n".join(_rank_row(rank, stat) for rank, stat in enumerate(stats, start=1))
        return f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<style>
* {{ box-sizing: border-box; }}
html, body {{ margin: 0; padding: 0; background: #111; }}
body {{
  width: {self.width}px;
  font-family: -apple-system, BlinkMacSystemFont, "PingFang SC", "Microsoft YaHei", Arial, sans-serif;
  color: #26313d;
}}
#rank-card {{
  width: {self.width - 40}px;
  margin: 20px;
  overflow: hidden;
  background: #fff;
  border-radius: 4px;
}}
.title {{
  padding: 22px 26px 20px;
  background: linear-gradient(90deg, #10b8c8, #9edfe3);
  color: #fff;
  font-size: 32px;
  font-weight: 780;
  line-height: 1;
  text-shadow: 0 1px 2px rgba(0,0,0,.18);
}}
.sub {{
  margin-top: 8px;
  font-size: 14px;
  font-weight: 500;
  opacity: .92;
}}
table {{
  width: 100%;
  border-collapse: collapse;
  table-layout: fixed;
}}
thead th {{
  height: 58px;
  color: #05aebd;
  background: #fff;
  font-size: 22px;
  font-weight: 780;
  text-align: left;
  text-shadow: 0 1px 2px rgba(0,0,0,.16);
}}
tbody tr {{ height: 54px; background: #fff; }}
tbody tr:nth-child(even) {{ background: #ececec; }}
tbody tr.gold {{ background: #ffe15a; }}
tbody tr.silver {{ background: #8f989b; color: #fff; }}
tbody tr.bronze {{ background: #c8835f; color: #fff; }}
td {{
  padding: 8px 10px;
  font-size: 22px;
  font-weight: 650;
  vertical-align: middle;
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
}}
.rank, .solved, .rating {{ text-align: center; }}
.rank {{ width: 78px; color: rgba(38,49,61,.55); }}
.nick {{ width: 386px; }}
.solved {{ width: 138px; }}
.rating {{ width: 138px; }}
.user {{
  display: flex;
  align-items: center;
  min-width: 0;
  gap: 12px;
}}
.avatar {{
  width: 34px;
  height: 34px;
  border-radius: 50%;
  flex: 0 0 auto;
  background: #dfe3e8;
}}
.name {{
  min-width: 0;
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
}}
</style>
</head>
<body>
<section id="rank-card">
  <div class="title">Ranklist<div class="sub">Group {group_id}</div></div>
  <table>
    <thead>
      <tr>
        <th class="rank">#</th>
        <th class="nick">Nickname</th>
        <th class="solved"># Solved</th>
        <th class="rating">Rating</th>
      </tr>
    </thead>
    <tbody>{rows}</tbody>
  </table>
</section>
</body>
</html>"""


def _rank_row(rank: int, stat: UserStat) -> str:
    row_class = {1: "gold", 2: "silver", 3: "bronze"}.get(rank, "")
    avatar_url = f"https://q1.qlogo.cn/g?b=qq&nk={stat.user_id}&s=100"
    return (
        f"<tr class=\"{row_class}\">"
        f"<td class=\"rank\">{rank}</td>"
        "<td class=\"nick\"><div class=\"user\">"
        f"<img class=\"avatar\" src=\"{html.escape(avatar_url)}\">"
        f"<span class=\"name\">{html.escape(stat.display_name)}</span>"
        "</div></td>"
        f"<td class=\"solved\">{stat.solved_count}</td>"
        f"<td class=\"rating\">{leaderboard_rating(stat.solved_ratings, stat.rating):.2f}</td>"
        "</tr>"
    )


def _stats_hash(stats: Sequence[UserStat]) -> str:
    text = "|".join(
        f"{stat.user_id}:{stat.solved_count}:{stat.rating:.2f}:{','.join(map(str, stat.solved_ratings))}"
        for stat in stats
    )
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:10]
