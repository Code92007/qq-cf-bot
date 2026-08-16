from __future__ import annotations

import json
import re
from dataclasses import replace
from typing import Any, Dict, Optional, Sequence

from .llm import LLMProviderConfig, OpenAICompatibleTextClient
from .models import ProblemStatement


class OpenAIStatementTranslator:
    def __init__(
        self,
        api_url: str,
        api_key: str,
        model: str,
        wire_api: str = "chat_completions",
        timeout_seconds: int = 60,
        max_chars: int = 60_000,
        enabled: bool = False,
        providers: Optional[Sequence[LLMProviderConfig]] = None,
    ) -> None:
        self.client = OpenAICompatibleTextClient(
            api_url=api_url,
            api_key=api_key,
            model=model,
            wire_api=wire_api,
            timeout_seconds=timeout_seconds,
            providers=providers,
        )
        self.timeout_seconds = timeout_seconds
        self.max_chars = max_chars
        self.enabled = enabled

    @property
    def configured(self) -> bool:
        return bool(self.enabled and self.client.configured)

    def translate_statement(self, statement: ProblemStatement) -> ProblemStatement:
        if not self.configured:
            return statement

        fields = {
            "title": statement.title,
            "description": statement.description,
            "input_format": statement.input_format,
            "output_format": statement.output_format,
            "hint": statement.hint,
        }
        source = json.dumps(fields, ensure_ascii=False)
        if len(source) > self.max_chars:
            raise RuntimeError(f"statement is too large to translate safely: {len(source)} chars")

        content = self.client.complete_json(_STATEMENT_TRANSLATE_PROMPT, source)
        translated = _parse_json_object(content)
        return replace(
            statement,
            title=_field(translated, "title", statement.title),
            description=_field(translated, "description", statement.description),
            input_format=_field(translated, "input_format", statement.input_format),
            output_format=_field(translated, "output_format", statement.output_format),
            hint=_field(translated, "hint", statement.hint),
        )

    def translate_title(self, title: str) -> str:
        if not self.configured or not title.strip():
            return title
        source = json.dumps({"title": title.strip()}, ensure_ascii=False)
        content = self.client.complete_json(_TITLE_TRANSLATE_PROMPT, source)
        translated = _parse_json_object(content)
        return _field(translated, "title", title)


_STATEMENT_TRANSLATE_PROMPT = (
    "你是算法竞赛题面翻译器。把 Codeforces 英文题面翻译成简体中文。"
    "即使标题或章节名已经是中文，只要正文仍包含英文自然语言，也必须完整翻译正文。"
    "保留 HTML 标签、LaTeX/数学公式、变量名、复杂度记号、代码片段、样例输入输出和链接。"
    "不要解释题意，不要补充解法，不要改变题面含义。"
    "只返回 JSON 对象，键必须是 title, description, input_format, output_format, hint。"
    "值里可以保留原 HTML 标签。"
)


_TITLE_TRANSLATE_PROMPT = (
    "你是算法竞赛题面翻译器。把 Codeforces 英文题目标题翻译成简体中文。"
    "保留人名、专有名词、变量名和题号，不要解释题意。"
    "只返回 JSON 对象，格式为 {\"title\": string}。"
)


def _field(payload: Dict[str, Any], key: str, fallback: str) -> str:
    value = payload.get(key)
    if value is None:
        return fallback
    value = str(value).strip()
    return value if value else fallback


def _parse_json_object(text: str) -> dict:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            raise
        return json.loads(match.group(0))
