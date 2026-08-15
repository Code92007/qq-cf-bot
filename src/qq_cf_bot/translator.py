from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from dataclasses import replace
from typing import Any, Dict

from .models import ProblemStatement


class OpenAIStatementTranslator:
    def __init__(
        self,
        api_url: str,
        api_key: str,
        model: str,
        timeout_seconds: int = 60,
        max_chars: int = 24_000,
        enabled: bool = False,
    ) -> None:
        self.api_url = api_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.max_chars = max_chars
        self.enabled = enabled

    @property
    def configured(self) -> bool:
        return bool(self.enabled and self.api_url and self.api_key and self.model)

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

        payload = {
            "model": self.model,
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "你是算法竞赛题面翻译器。把 Codeforces 英文题面翻译成简体中文。"
                        "保留 HTML 标签、LaTeX/数学公式、变量名、复杂度记号、代码片段、样例输入输出和链接。"
                        "不要解释题意，不要补充解法，不要改变题面含义。"
                        "只返回 JSON 对象，键必须是 title, description, input_format, output_format, hint。"
                        "值里可以保留原 HTML 标签。"
                    ),
                },
                {"role": "user", "content": source},
            ],
        }
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(
            self.api_url,
            data=data,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
                "User-Agent": "qq-cf-bot/0.1",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                body = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            error_body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"translation API returned HTTP {exc.code}: {error_body}") from exc

        result = json.loads(body)
        content = result["choices"][0]["message"]["content"]
        translated = _parse_json_object(content)
        return replace(
            statement,
            title=_field(translated, "title", statement.title),
            description=_field(translated, "description", statement.description),
            input_format=_field(translated, "input_format", statement.input_format),
            output_format=_field(translated, "output_format", statement.output_format),
            hint=_field(translated, "hint", statement.hint),
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
