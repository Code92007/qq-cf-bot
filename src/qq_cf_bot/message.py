from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Optional


_CQ_CODE_RE = re.compile(r"\[CQ:[^\]]+\]")
_FENCED_CODE_RE = re.compile(r"```(?P<language>[A-Za-z0-9_+#.-]*)\s*\n(?P<source>.*?)```", re.DOTALL)
_CODE_HINT_RE = re.compile(
    r"^\s*(#include\b|using\s+namespace\b|int\s+main\s*\(|import\s+\w+|from\s+\w+\s+import\b|"
    r"public\s+class\b|package\s+\w+|fn\s+main\s*\(|use\s+std::)",
    re.MULTILINE,
)


@dataclass(frozen=True)
class ParsedCommand:
    name: str
    arg: str = ""


@dataclass(frozen=True)
class ParsedCodeSubmission:
    language: str
    source: str


def extract_plain_text(message: Any) -> str:
    if isinstance(message, str):
        return _CQ_CODE_RE.sub("", message)

    if isinstance(message, list):
        parts = []
        for segment in message:
            if not isinstance(segment, dict):
                continue
            if segment.get("type") == "text":
                data = segment.get("data") or {}
                parts.append(str(data.get("text", "")))
        return "".join(parts)

    return ""


def is_new_command(message: Any) -> bool:
    command = parse_command(message)
    return command is not None and command.name == "new"


def parse_command(message: Any) -> Optional[ParsedCommand]:
    text = extract_plain_text(message).strip()
    if text.startswith("／"):
        text = "/" + text[1:]
    if not text:
        return None
    if not text.startswith("/"):
        return None

    parts = text.split(maxsplit=1)
    raw_name = parts[0][1:].strip().lower()
    if not raw_name:
        return None
    arg = parts[1].strip() if len(parts) > 1 else ""
    return ParsedCommand(raw_name, arg)


def parse_code_submission(text: str, default_language: str = "cpp") -> Optional[ParsedCodeSubmission]:
    text = text.strip()
    if not text:
        return None

    fence = _FENCED_CODE_RE.search(text)
    if fence:
        language = (fence.group("language") or default_language).strip().lower()
        source = fence.group("source").strip("\n")
        return ParsedCodeSubmission(language=language or default_language, source=source)

    lines = text.splitlines()
    if lines and _looks_like_language_alias(lines[0]) and len(lines) >= 2:
        language = lines[0].strip().lower()
        source = "\n".join(lines[1:]).strip("\n")
        return ParsedCodeSubmission(language=language, source=source)

    if looks_like_code_text(text):
        return ParsedCodeSubmission(language=default_language, source=text)
    return None


def looks_like_code_submission(message: Any) -> bool:
    return looks_like_code_text(extract_plain_text(message))


def looks_like_code_text(text: str) -> bool:
    if len(text.strip()) < 20:
        return False
    return bool(_FENCED_CODE_RE.search(text) or _CODE_HINT_RE.search(text))


def _looks_like_language_alias(text: str) -> bool:
    normalized = text.strip().lower()
    return normalized in {
        "cpp",
        "c++",
        "gnu++17",
        "gnu++20",
        "gnu++23",
        "c",
        "python",
        "python3",
        "py",
        "pypy",
        "java",
        "kotlin",
        "kt",
        "rust",
        "rs",
        "go",
    }
