from __future__ import annotations

import json
import re
from dataclasses import replace
from typing import Any, Dict, Optional, Sequence

from .llm import LLMProviderConfig, OpenAICompatibleTextClient
from .models import ProblemStatement
from .prompt_skills import STATEMENT_RENDERING_SKILL
from .renderer import normalize_statement_markup


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

        first = self._translate_statement_once(statement, source, _STATEMENT_TRANSLATE_PROMPT)
        if not _looks_untranslated(first):
            return first

        retry_source = json.dumps(
            {
                "previous_translation_still_untranslated": {
                    "title": first.title,
                    "description": first.description,
                    "input_format": first.input_format,
                    "output_format": first.output_format,
                    "hint": first.hint,
                },
                "original": fields,
            },
            ensure_ascii=False,
        )
        if len(retry_source) > self.max_chars:
            return first
        return self._translate_statement_once(statement, retry_source, _STATEMENT_RETRANSLATE_PROMPT)

    def translate_title(self, title: str) -> str:
        if not self.configured or not title.strip():
            return title
        source = json.dumps({"title": title.strip()}, ensure_ascii=False)
        content = self.client.complete_json(_TITLE_TRANSLATE_PROMPT, source)
        translated = _parse_json_object(content)
        return _field(translated, "title", title)

    def _translate_statement_once(self, statement: ProblemStatement, source: str, prompt: str) -> ProblemStatement:
        content = self.client.complete_json(prompt, source)
        translated = _parse_json_object(content)
        return replace(
            statement,
            title=_field(translated, "title", statement.title),
            description=normalize_statement_markup(_field(translated, "description", statement.description)),
            input_format=normalize_statement_markup(_field(translated, "input_format", statement.input_format)),
            output_format=normalize_statement_markup(_field(translated, "output_format", statement.output_format)),
            hint=normalize_statement_markup(_field(translated, "hint", statement.hint)),
        )


_STATEMENT_TRANSLATE_PROMPT = (
    STATEMENT_RENDERING_SKILL
    + "\n\n"
    "你是算法竞赛题面翻译器。把 Codeforces 英文题面翻译成简体中文。"
    "即使标题或章节名已经是中文，只要正文仍包含英文自然语言，也必须完整翻译正文。"
    "保留 HTML 标签、LaTeX/数学公式、变量名、复杂度记号、代码片段、样例输入输出和链接。"
    "LaTeX 公式内部只能翻译自然语言，必须原样保留反斜杠命令和分隔符；"
    "例如 \\lfloor、\\lceil、\\frac、\\dfrac、\\ldots、\\le、\\ge、\\lt、\\gt、\\mid、\\to、\\rightarrow、\\sum、\\texttt 不得改写、拆散或去掉反斜杠。"
    "严格递增必须译为“小于/严格递增”，不能误译成整除；\\mid 才表示整除关系。"
    "样例解释中的状态变化箭头要写成 →，不要留下英文 arrow。"
    "独占一行的公式必须继续独占一行，例如 \\sum_{i=2}^{n} v(i,a_i) 不得拍平成正文。"
    "不要把 $$$...$$$、$...$ 或 \\(...\\) 改成别的格式。"
    "不要解释题意，不要补充解法，不要改变题面含义。"
    "只返回 JSON 对象，键必须是 title, description, input_format, output_format, hint。"
    "值里可以保留原 HTML 标签。"
)


_STATEMENT_RETRANSLATE_PROMPT = (
    STATEMENT_RENDERING_SKILL
    + "\n\n"
    "上一轮输出仍包含大量英文自然语言，视为失败。请重新翻译成简体中文。"
    "必须把 description、input_format、output_format、hint 中的英文句子翻译成中文；"
    "人名、变量名、YES/NO、代码、样例和 LaTeX 公式保持原样。"
    "对于数学表达式，保留 $$$...$$$、$...$、\\(...\\)、\\[...\\] 分隔符和命令，"
    "尤其要保留 a_{b_i}、b_{a_i}、p_{a_i}、\\le、\\lt、\\mid、\\to、\\rightarrow、\\sum_{i=2}^{n}、\\cdot、10^9 这类结构。"
    "不要输出 b^k mid x、a_i lt a_{i+1}、Σ_i=2^n、[1,2,3] arrow [2,3,4] 这类损坏形式。"
    "只返回 JSON 对象，键必须是 title, description, input_format, output_format, hint。"
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


def _looks_untranslated(statement: ProblemStatement) -> bool:
    text = " ".join(
        [
            statement.description,
            statement.input_format,
            statement.output_format,
            statement.hint,
        ]
    )
    text = re.sub(r"\${1,3}.*?\${1,3}", " ", text, flags=re.DOTALL)
    text = re.sub(r"\\\(.+?\\\)|\\\[.+?\\\]", " ", text, flags=re.DOTALL)
    text = re.sub(r"<[^>]+>", " ", text)
    cjk_chars = len(re.findall(r"[\u4e00-\u9fff]", text))
    english_words = re.findall(r"[A-Za-z][A-Za-z']{2,}", text)
    if len(english_words) < 10:
        return False
    if cjk_chars == 0:
        return True
    return len(english_words) >= 25 and len(english_words) > cjk_chars / 3
