from __future__ import annotations

import html
import re


def normalize_sample_block(raw_html: object) -> str:
    """Convert Codeforces/Luogu sample HTML into plain text while keeping lines."""
    text = str(raw_html or "")
    text = re.sub(r"(?i)<br\s*/?>", "\n", text)
    text = re.sub(r"(?i)</div>\s*<div[^>]*>", "\n", text)
    text = re.sub(r"(?i)<div[^>]*>", "", text)
    text = re.sub(r"(?i)</div>", "\n", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = html.unescape(text).replace("\r", "")
    lines = [line.rstrip() for line in text.split("\n")]
    while lines and lines[0] == "":
        lines.pop(0)
    while lines and lines[-1] == "":
        lines.pop()
    return "\n".join(lines)


def normalize_embedded_pre_html(raw_html: str) -> str:
    text = normalize_sample_block(raw_html)
    return f"<pre>{html.escape(text)}</pre>"
