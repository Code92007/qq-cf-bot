from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from typing import Sequence

from .models import CFProblem, JudgeResult, ProblemStatement, SolutionReference


class SolutionJudge:
    def __init__(
        self,
        api_url: str,
        api_key: str,
        model: str,
        timeout_seconds: int,
        max_statement_chars: int,
        max_solution_context_chars: int,
        enabled: bool = True,
    ) -> None:
        self.api_url = api_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.max_statement_chars = max_statement_chars
        self.max_solution_context_chars = max_solution_context_chars
        self.enabled = enabled

    @property
    def configured(self) -> bool:
        return bool(self.enabled and self.api_url and self.api_key and self.model)

    def judge(
        self,
        problem: CFProblem,
        statement: ProblemStatement,
        submission: str,
        solution_references: Sequence[SolutionReference] = (),
        solution_context: str = "",
    ) -> JudgeResult:
        if not self.configured:
            raise RuntimeError("judge model is not configured")
        if not submission.strip():
            return JudgeResult(False, "提交内容为空。")

        payload = {
            "model": self.model,
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "你是算法竞赛题解审核员。你需要根据题面判断群友口头提交的做法是否足以通过本题。"
                        "你会同时收到已缓存的参考题解或 AC 代码片段；必须优先用这些参考材料校对算法方向、关键不变量、复杂度和边界条件。"
                        "只返回 JSON 对象，格式为 {\"accepted\": boolean, \"reason\": string}。"
                        "判定必须严格：复杂度不满足、关键边界漏掉、逻辑错误或描述过于含糊，都算不通过。"
                        "如果参考题解不足以覆盖本题，也要依据题面独立判断，不要假装已经校对。"
                        "如果不通过，reason 用中文简要指出具体错误，不要给出正确做法、提示、改法或完整思路。"
                        "如果通过，reason 写“通过”。"
                    ),
                },
                {
                    "role": "user",
                    "content": self._build_prompt(
                        problem,
                        statement,
                        submission,
                        solution_references,
                        solution_context,
                    ),
                },
            ],
        }
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
            "User-Agent": "qq-cf-bot/0.1",
        }
        request = urllib.request.Request(self.api_url, data=data, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                body = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            error_body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"judge API returned HTTP {exc.code}: {error_body}") from exc

        result = json.loads(body)
        content = result["choices"][0]["message"]["content"]
        parsed = _parse_json_object(content)
        return JudgeResult(
            accepted=bool(parsed.get("accepted")),
            reason=str(parsed.get("reason") or ("通过" if parsed.get("accepted") else "做法不完整。")).strip(),
        )

    def _build_prompt(
        self,
        problem: CFProblem,
        statement: ProblemStatement,
        submission: str,
        solution_references: Sequence[SolutionReference],
        solution_context: str,
    ) -> str:
        statement_text = "\n\n".join(
            part
            for part in [
                f"题号：{problem.luogu_pid} / {problem.cf_id}",
                f"标题：{statement.title or problem.name}",
                f"难度：{problem.rating}",
                f"标签：{', '.join(problem.tags)}",
                "题目描述：\n" + statement.description,
                "输入格式：\n" + statement.input_format,
                "输出格式：\n" + statement.output_format,
                _format_samples(statement),
                "注释：\n" + statement.hint if statement.hint else "",
            ]
            if part.strip()
        )
        statement_text = _truncate(statement_text, self.max_statement_chars)
        reference_text = _format_solution_references(
            solution_references,
            solution_context,
            self.max_solution_context_chars,
        )
        return (
            f"{statement_text}\n\n"
            f"已缓存参考材料：\n{reference_text}\n\n"
            f"群友提交的口头做法：\n{submission.strip()}"
        )


def _format_samples(statement: ProblemStatement) -> str:
    if not statement.samples:
        return ""
    chunks = []
    for idx, (sample_input, sample_output) in enumerate(statement.samples[:3], start=1):
        chunks.append(f"样例 {idx} 输入：\n{sample_input}\n样例 {idx} 输出：\n{sample_output}")
    return "\n\n".join(chunks)


def _truncate(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "\n\n[题面过长，后续内容已截断]"


def _format_solution_references(
    references: Sequence[SolutionReference],
    solution_context: str,
    max_chars: int,
) -> str:
    if not references:
        return "暂无缓存题解。请只依据题面严格判断。"
    header = "缓存题解数量：" + str(len(references))
    if not solution_context.strip():
        return header
    return header + "\n\n" + _truncate(solution_context, max_chars)


def _parse_json_object(text: str) -> dict:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            raise
        return json.loads(match.group(0))
