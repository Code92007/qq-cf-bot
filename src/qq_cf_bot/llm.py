from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any, Dict, Iterable, Optional


SUPPORTED_WIRE_APIS = frozenset({"chat_completions", "responses"})


class OpenAICompatibleTextClient:
    def __init__(
        self,
        api_url: str,
        api_key: str,
        model: str,
        wire_api: str = "chat_completions",
        timeout_seconds: int = 60,
    ) -> None:
        self.wire_api = normalize_wire_api(wire_api)
        self.api_url = endpoint_url(api_url, self.wire_api)
        self.api_key = api_key
        self.model = model
        self.timeout_seconds = timeout_seconds

    @property
    def configured(self) -> bool:
        return bool(self.api_url and self.api_key and self.model)

    def complete_json(self, system_prompt: str, user_prompt: str) -> str:
        if not self.configured:
            raise RuntimeError("model API is not configured")

        payload = self._payload(system_prompt, user_prompt)
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
            raise RuntimeError(f"model API returned HTTP {exc.code}: {error_body}") from exc

        result = json.loads(body)
        error = result.get("error")
        if error:
            raise RuntimeError(f"model API returned error: {error!r}")
        return extract_text(result)

    def _payload(self, system_prompt: str, user_prompt: str) -> Dict[str, Any]:
        if self.wire_api == "responses":
            return {
                "model": self.model,
                "temperature": 0,
                "instructions": system_prompt,
                "input": [{"role": "user", "content": [{"type": "input_text", "text": user_prompt}]}],
                "text": {"format": {"type": "json_object"}},
            }
        return {
            "model": self.model,
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }


def normalize_wire_api(value: str) -> str:
    normalized = value.strip().lower().replace("-", "_")
    aliases = {
        "chat": "chat_completions",
        "chat_completion": "chat_completions",
        "chat_completions": "chat_completions",
        "response": "responses",
        "responses": "responses",
    }
    if normalized not in aliases:
        raise ValueError("wire API must be either 'chat_completions' or 'responses'")
    return aliases[normalized]


def infer_wire_api(api_url: str, default: str = "chat_completions") -> str:
    url = api_url.rstrip("/")
    if url.endswith("/responses"):
        return "responses"
    if url.endswith("/chat/completions"):
        return "chat_completions"
    return normalize_wire_api(default)


def endpoint_url(api_url: str, wire_api: str) -> str:
    url = api_url.rstrip("/")
    if not url:
        return ""
    wire_api = normalize_wire_api(wire_api)
    if wire_api == "responses":
        if url.endswith("/chat/completions"):
            return url[: -len("/chat/completions")] + "/responses"
        if url.endswith("/responses"):
            return url
        return url + "/responses"

    if url.endswith("/responses"):
        return url[: -len("/responses")] + "/chat/completions"
    if url.endswith("/chat/completions"):
        return url
    return url + "/chat/completions"


def extract_text(result: Dict[str, Any]) -> str:
    chat_text = _extract_chat_text(result)
    if chat_text is not None:
        return chat_text

    output_text = result.get("output_text")
    if isinstance(output_text, str) and output_text.strip():
        return output_text

    texts = list(_iter_response_output_text(result.get("output")))
    if texts:
        return "\n".join(texts)
    raise RuntimeError(f"model API response did not contain text output: {result!r}")


def _extract_chat_text(result: Dict[str, Any]) -> Optional[str]:
    choices = result.get("choices")
    if not isinstance(choices, list) or not choices:
        return None
    first = choices[0]
    if not isinstance(first, dict):
        return None
    message = first.get("message")
    if not isinstance(message, dict):
        return None
    content = message.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict) and isinstance(item.get("text"), str):
                parts.append(item["text"])
        if parts:
            return "\n".join(parts)
    return None


def _iter_response_output_text(output: Any) -> Iterable[str]:
    if not isinstance(output, list):
        return
    for item in output:
        if not isinstance(item, dict):
            continue
        content = item.get("content")
        if isinstance(content, str):
            yield content
            continue
        if not isinstance(content, list):
            continue
        for part in content:
            if not isinstance(part, dict):
                continue
            if part.get("type") in {"output_text", "text"} and isinstance(part.get("text"), str):
                yield part["text"]
