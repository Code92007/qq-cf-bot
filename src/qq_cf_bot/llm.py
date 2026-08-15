from __future__ import annotations

import base64
import hashlib
import json
import os
import socket
import ssl
import struct
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Protocol, Tuple


SUPPORTED_WIRE_APIS = frozenset({"chat_completions", "responses", "responses_stream", "responses_websocket"})
RESPONSES_WEBSOCKET_BETA = "responses_websockets=2026-02-06"
JSON_OUTPUT_SUFFIX = "\n\nOutput requirement: return only valid json."


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
        self._transport = _make_transport(
            api_url=api_url,
            api_key=api_key,
            model=model,
            wire_api=self.wire_api,
            timeout_seconds=timeout_seconds,
        )

    @property
    def configured(self) -> bool:
        return self._transport.configured

    def complete_json(self, system_prompt: str, user_prompt: str) -> str:
        return self._transport.complete_json(system_prompt, user_prompt)

    def _payload(self, system_prompt: str, user_prompt: str) -> Dict[str, Any]:
        return _payload(self.wire_api, self.model, system_prompt, user_prompt)


class _TextCompletionTransport(Protocol):
    @property
    def configured(self) -> bool:
        ...

    def complete_json(self, system_prompt: str, user_prompt: str) -> str:
        ...


@dataclass(frozen=True)
class _TransportConfig:
    api_url: str
    api_key: str
    model: str
    wire_api: str
    timeout_seconds: int


class _BaseTransport:
    def __init__(self, config: _TransportConfig) -> None:
        self.config = config
        self.api_url = endpoint_url(config.api_url, config.wire_api)

    @property
    def configured(self) -> bool:
        return bool(self.api_url and self.config.api_key and self.config.model)


class _HTTPTransport(_BaseTransport):
    def complete_json(self, system_prompt: str, user_prompt: str) -> str:
        if not self.configured:
            raise RuntimeError("model API is not configured")

        payload = _payload(self.config.wire_api, self.config.model, system_prompt, user_prompt)
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(
            self.api_url,
            data=data,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.config.api_key}",
                "User-Agent": "qq-cf-bot/0.1",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.config.timeout_seconds) as response:
                body = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            error_body = exc.read().decode("utf-8", errors="replace")
            if self.config.wire_api == "responses" and exc.code == 426 and _mentions_upgrade_required(error_body):
                return _ResponsesStreamTransport(
                    _TransportConfig(
                        api_url=self.config.api_url,
                        api_key=self.config.api_key,
                        model=self.config.model,
                        wire_api="responses_stream",
                        timeout_seconds=self.config.timeout_seconds,
                    )
                ).complete_json(system_prompt, user_prompt)
            raise RuntimeError(f"model API returned HTTP {exc.code}: {error_body}") from exc

        result = json.loads(body)
        error = result.get("error")
        if error:
            raise RuntimeError(f"model API returned error: {error!r}")
        return extract_text(result)


class _ResponsesStreamTransport(_BaseTransport):
    def complete_json(self, system_prompt: str, user_prompt: str) -> str:
        if not self.configured:
            raise RuntimeError("model API is not configured")

        payload = _responses_payload(self.config.model, system_prompt, user_prompt, include_temperature=False)
        payload["stream"] = True
        payload["store"] = False
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(
            self.api_url,
            data=data,
            headers={
                "Accept": "text/event-stream",
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.config.api_key}",
                "User-Agent": "qq-cf-bot/0.1",
                "x-client-request-id": str(uuid.uuid4()),
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.config.timeout_seconds) as response:
                return _read_responses_sse_json(response, self.config.timeout_seconds)
        except urllib.error.HTTPError as exc:
            error_body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"model API returned HTTP {exc.code}: {error_body}") from exc


class _ResponsesWebSocketTransport(_BaseTransport):
    def complete_json(self, system_prompt: str, user_prompt: str) -> str:
        if not self.configured:
            raise RuntimeError("model API is not configured")

        payload = _responses_payload(self.config.model, system_prompt, user_prompt, include_temperature=False)
        event = {"type": "response.create", **payload}
        with _WebSocketConnection(
            self.api_url,
            headers={
                "Authorization": f"Bearer {self.config.api_key}",
                "OpenAI-Beta": RESPONSES_WEBSOCKET_BETA,
                "x-client-request-id": str(uuid.uuid4()),
                "x-openai-internal-codex-responses-lite": "true",
                "User-Agent": "qq-cf-bot/0.1",
            },
            timeout_seconds=self.config.timeout_seconds,
        ) as websocket:
            websocket.send_json(event)
            return _read_responses_websocket_json(websocket, self.config.timeout_seconds)


def _make_transport(
    api_url: str,
    api_key: str,
    model: str,
    wire_api: str,
    timeout_seconds: int,
) -> _TextCompletionTransport:
    config = _TransportConfig(
        api_url=api_url,
        api_key=api_key,
        model=model,
        wire_api=normalize_wire_api(wire_api),
        timeout_seconds=timeout_seconds,
    )
    if config.wire_api == "responses_stream":
        return _ResponsesStreamTransport(config)
    if config.wire_api == "responses_websocket":
        return _ResponsesWebSocketTransport(config)
    return _HTTPTransport(config)


def _payload(wire_api: str, model: str, system_prompt: str, user_prompt: str) -> Dict[str, Any]:
    normalized = normalize_wire_api(wire_api)
    if normalized in {"responses", "responses_stream", "responses_websocket"}:
        return _responses_payload(model, system_prompt, user_prompt, include_temperature=normalized == "responses")
    return {
        "model": model,
        "temperature": 0,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    }


def _responses_payload(
    model: str,
    system_prompt: str,
    user_prompt: str,
    include_temperature: bool = True,
) -> Dict[str, Any]:
    payload = {
        "model": model,
        "instructions": system_prompt,
        "input": [{"role": "user", "content": [{"type": "input_text", "text": user_prompt + JSON_OUTPUT_SUFFIX}]}],
        "text": {"format": {"type": "json_object"}},
    }
    if include_temperature:
        payload["temperature"] = 0
    return payload


def normalize_wire_api(value: str) -> str:
    normalized = value.strip().lower().replace("-", "_")
    aliases = {
        "chat": "chat_completions",
        "chat_completion": "chat_completions",
        "chat_completions": "chat_completions",
        "response": "responses",
        "responses": "responses",
        "responses_http": "responses",
        "response_stream": "responses_stream",
        "responses_stream": "responses_stream",
        "response_sse": "responses_stream",
        "responses_sse": "responses_stream",
        "sse": "responses_stream",
        "response_websocket": "responses_websocket",
        "responses_websocket": "responses_websocket",
        "response_ws": "responses_websocket",
        "responses_ws": "responses_websocket",
        "websocket": "responses_websocket",
        "ws": "responses_websocket",
    }
    if normalized not in aliases:
        raise ValueError(
            "wire API must be one of 'chat_completions', 'responses', 'responses_stream', or 'responses_websocket'"
        )
    return aliases[normalized]


def infer_wire_api(api_url: str, default: str = "chat_completions") -> str:
    url = api_url.rstrip("/")
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme in {"ws", "wss"}:
        return "responses_websocket"
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
    if wire_api in {"responses", "responses_stream", "responses_websocket"}:
        url = _coerce_scheme(url, websocket=wire_api == "responses_websocket")
        if url.endswith("/chat/completions"):
            return url[: -len("/chat/completions")] + "/responses"
        if url.endswith("/responses"):
            return url
        return url + "/responses"

    url = _coerce_scheme(url, websocket=False)
    if url.endswith("/responses"):
        return url[: -len("/responses")] + "/chat/completions"
    if url.endswith("/chat/completions"):
        return url
    return url + "/chat/completions"


def _coerce_scheme(url: str, websocket: bool) -> str:
    if websocket:
        if url.startswith("https://"):
            return "wss://" + url[len("https://") :]
        if url.startswith("http://"):
            return "ws://" + url[len("http://") :]
        return url
    if url.startswith("wss://"):
        return "https://" + url[len("wss://") :]
    if url.startswith("ws://"):
        return "http://" + url[len("ws://") :]
    return url


def _mentions_upgrade_required(text: str) -> bool:
    lowered = text.lower()
    return "upgrade" in lowered or "websocket" in lowered or "event-stream" in lowered


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


class _WebSocketConnection:
    def __init__(self, url: str, headers: Dict[str, str], timeout_seconds: int) -> None:
        self.url = url
        self.headers = headers
        self.timeout_seconds = timeout_seconds
        self._socket: Optional[socket.socket] = None

    def __enter__(self) -> "_WebSocketConnection":
        self._connect()
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self.close()

    def _connect(self) -> None:
        parsed = urllib.parse.urlsplit(self.url)
        if parsed.scheme not in {"ws", "wss"}:
            raise RuntimeError(f"responses_websocket requires ws:// or wss:// URL, got {self.url!r}")
        if not parsed.hostname:
            raise RuntimeError(f"responses_websocket URL is missing a host: {self.url!r}")

        port = parsed.port or (443 if parsed.scheme == "wss" else 80)
        path = parsed.path or "/"
        if parsed.query:
            path += "?" + parsed.query

        raw_socket = socket.create_connection((parsed.hostname, port), timeout=self.timeout_seconds)
        if parsed.scheme == "wss":
            raw_socket = ssl.create_default_context().wrap_socket(raw_socket, server_hostname=parsed.hostname)
        raw_socket.settimeout(self.timeout_seconds)

        websocket_key = base64.b64encode(os.urandom(16)).decode("ascii")
        host = parsed.hostname if parsed.port is None else f"{parsed.hostname}:{port}"
        request_headers = {
            "Host": host,
            "Upgrade": "websocket",
            "Connection": "Upgrade",
            "Sec-WebSocket-Key": websocket_key,
            "Sec-WebSocket-Version": "13",
            **self.headers,
        }
        request = [f"GET {path} HTTP/1.1"]
        request.extend(f"{key}: {value}" for key, value in request_headers.items())
        request.append("\r\n")
        raw_socket.sendall("\r\n".join(request).encode("utf-8"))

        response_head = self._read_http_head(raw_socket)
        status_line = response_head.splitlines()[0] if response_head else ""
        if " 101 " not in status_line:
            raw_socket.close()
            raise RuntimeError(f"responses_websocket handshake failed: {response_head}")

        accept = _header_value(response_head, "Sec-WebSocket-Accept")
        expected_accept = base64.b64encode(
            hashlib.sha1((websocket_key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode("ascii")).digest()
        ).decode("ascii")
        if accept and accept != expected_accept:
            raw_socket.close()
            raise RuntimeError("responses_websocket handshake failed: Sec-WebSocket-Accept mismatch")

        self._socket = raw_socket

    def _read_http_head(self, raw_socket: socket.socket) -> str:
        chunks = b""
        while b"\r\n\r\n" not in chunks:
            chunk = raw_socket.recv(4096)
            if not chunk:
                break
            chunks += chunk
            if len(chunks) > 64 * 1024:
                raise RuntimeError("responses_websocket handshake header is too large")
        return chunks.decode("utf-8", errors="replace").split("\r\n\r\n", 1)[0]

    def send_json(self, payload: Dict[str, Any]) -> None:
        self._send_frame(0x1, json.dumps(payload, ensure_ascii=False).encode("utf-8"))

    def recv_text(self) -> str:
        parts: List[bytes] = []
        while True:
            fin, opcode, payload = self._recv_frame()
            if opcode == 0x8:
                raise RuntimeError(f"responses_websocket closed: {_close_reason(payload)}")
            if opcode == 0x9:
                self._send_frame(0xA, payload)
                continue
            if opcode == 0xA:
                continue
            if opcode not in {0x0, 0x1}:
                continue
            parts.append(payload)
            if fin:
                return b"".join(parts).decode("utf-8")

    def close(self) -> None:
        if self._socket is None:
            return
        try:
            self._send_frame(0x8, b"")
        except OSError:
            pass
        try:
            self._socket.close()
        finally:
            self._socket = None

    def _send_frame(self, opcode: int, payload: bytes) -> None:
        if self._socket is None:
            raise RuntimeError("responses_websocket is not connected")
        header = bytearray([0x80 | opcode])
        length = len(payload)
        if length < 126:
            header.append(0x80 | length)
        elif length < 1 << 16:
            header.append(0x80 | 126)
            header.extend(struct.pack("!H", length))
        else:
            header.append(0x80 | 127)
            header.extend(struct.pack("!Q", length))
        mask = os.urandom(4)
        header.extend(mask)
        masked = bytes(byte ^ mask[index % 4] for index, byte in enumerate(payload))
        self._socket.sendall(bytes(header) + masked)

    def _recv_frame(self) -> Tuple[bool, int, bytes]:
        if self._socket is None:
            raise RuntimeError("responses_websocket is not connected")
        header = _recv_exact(self._socket, 2)
        first, second = header
        fin = bool(first & 0x80)
        opcode = first & 0x0F
        masked = bool(second & 0x80)
        length = second & 0x7F
        if length == 126:
            length = struct.unpack("!H", _recv_exact(self._socket, 2))[0]
        elif length == 127:
            length = struct.unpack("!Q", _recv_exact(self._socket, 8))[0]
        mask = _recv_exact(self._socket, 4) if masked else b""
        payload = _recv_exact(self._socket, length) if length else b""
        if masked:
            payload = bytes(byte ^ mask[index % 4] for index, byte in enumerate(payload))
        return fin, opcode, payload


def _read_responses_websocket_json(websocket: _WebSocketConnection, timeout_seconds: int) -> str:
    deadline = time.monotonic() + timeout_seconds
    collector = _ResponseTextCollector()
    while time.monotonic() < deadline:
        event = json.loads(websocket.recv_text())
        result = collector.add(event)
        if result is not None:
            return result

    raise RuntimeError("model API websocket timed out before response.completed")


def _read_responses_sse_json(response: Any, timeout_seconds: int) -> str:
    deadline = time.monotonic() + timeout_seconds
    collector = _ResponseTextCollector()
    data_lines: List[str] = []

    def flush_event() -> Optional[str]:
        if not data_lines:
            return None
        data = "\n".join(data_lines).strip()
        data_lines.clear()
        if not data or data == "[DONE]":
            return None
        return collector.add(json.loads(data))

    for raw_line in response:
        if time.monotonic() > deadline:
            break
        line = raw_line.decode("utf-8", errors="replace").rstrip("\r\n")
        if not line:
            result = flush_event()
            if result is not None:
                return result
            continue
        if line.startswith("data:"):
            data_lines.append(line[5:].lstrip())

    result = flush_event()
    if result is not None:
        return result
    raise RuntimeError("model API stream ended before response.completed")


class _ResponseTextCollector:
    def __init__(self) -> None:
        self.text_parts: List[str] = []
        self.final_text: Optional[str] = None

    def add(self, event: Dict[str, Any]) -> Optional[str]:
        event_type = event.get("type")
        error = event.get("error")
        if error:
            raise RuntimeError(f"model API returned error: {error!r}")

        if event_type == "response.output_text.delta" and isinstance(event.get("delta"), str):
            self.text_parts.append(event["delta"])
            return None
        if event_type == "response.output_text.done" and isinstance(event.get("text"), str):
            self.final_text = event["text"]
            return None
        if event_type in {"response.completed", "response.done"}:
            response = event.get("response")
            if isinstance(response, dict):
                try:
                    return extract_text(response)
                except RuntimeError:
                    pass
            return self.final_text or "".join(self.text_parts)
        if event_type in {"response.failed", "response.incomplete"}:
            response_error = event.get("response", {}).get("error") if isinstance(event.get("response"), dict) else None
            raise RuntimeError(f"model API returned error: {response_error or event!r}")
        return None


def _recv_exact(raw_socket: socket.socket, size: int) -> bytes:
    chunks = b""
    while len(chunks) < size:
        chunk = raw_socket.recv(size - len(chunks))
        if not chunk:
            raise EOFError("responses_websocket stream closed unexpectedly")
        chunks += chunk
    return chunks


def _header_value(response_head: str, name: str) -> str:
    prefix = name.lower() + ":"
    for line in response_head.splitlines()[1:]:
        if line.lower().startswith(prefix):
            return line.split(":", 1)[1].strip()
    return ""


def _close_reason(payload: bytes) -> str:
    if len(payload) <= 2:
        return ""
    return payload[2:].decode("utf-8", errors="replace")
