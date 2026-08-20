from __future__ import annotations

import json
import logging
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Callable

from .message import is_at_only_mention, looks_like_code_submission, parse_command
from .models import GroupMessage


LOGGER = logging.getLogger(__name__)


class OneBotEventServer:
    def __init__(self, host: str, port: int, on_group_message: Callable[[GroupMessage], None]) -> None:
        self.host = host
        self.port = port
        self.on_group_message = on_group_message

    def serve_forever(self) -> None:
        callback = self.on_group_message

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self) -> None:
                if self.path != "/onebot":
                    self.send_error(404)
                    return

                try:
                    body = _read_request_body(self)
                    event = json.loads(body.decode("utf-8"))
                    _handle_event(event, callback)
                except Exception:
                    LOGGER.exception("failed to handle incoming OneBot event")

                self._json_response({"status": "ok"})

            def do_GET(self) -> None:
                if self.path == "/health":
                    self._json_response({"status": "ok"})
                else:
                    self.send_error(404)

            def log_message(self, format: str, *args: Any) -> None:
                LOGGER.debug("http: " + format, *args)

            def _json_response(self, payload: dict) -> None:
                data = json.dumps(payload).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

        server = ThreadingHTTPServer((self.host, self.port), Handler)
        LOGGER.info("listening on http://%s:%s/onebot", self.host, self.port)
        server.serve_forever()


def _read_request_body(handler: BaseHTTPRequestHandler) -> bytes:
    transfer_encoding = handler.headers.get("Transfer-Encoding", "").lower()
    if "chunked" in transfer_encoding:
        return _read_chunked_body(handler)

    length = int(handler.headers.get("Content-Length") or "0")
    return handler.rfile.read(length)


def _read_chunked_body(handler: BaseHTTPRequestHandler) -> bytes:
    chunks = []
    while True:
        size_line = handler.rfile.readline()
        if not size_line:
            break

        size_text = size_line.split(b";", 1)[0].strip()
        if not size_text:
            continue

        size = int(size_text, 16)
        if size == 0:
            _consume_trailing_headers(handler)
            break

        chunks.append(handler.rfile.read(size))
        handler.rfile.read(2)
    return b"".join(chunks)


def _consume_trailing_headers(handler: BaseHTTPRequestHandler) -> None:
    while True:
        line = handler.rfile.readline()
        if line in {b"", b"\r\n", b"\n"}:
            return


def _handle_event(event: dict, callback: Callable[[GroupMessage], None]) -> None:
    if event.get("post_type") != "message":
        return
    if event.get("message_type") != "group":
        return

    message = event.get("message")
    at_only = is_at_only_mention(message, event.get("self_id"))
    command = parse_command(message)
    direct_code = command is None and looks_like_code_submission(message)
    if command is None and not at_only and not direct_code:
        return
    if at_only:
        message = "/help"
        command = parse_command(message)

    LOGGER.info(
        "onebot command ingress group=%s user=%s message_id=%s command=%s",
        event.get("group_id"),
        event.get("user_id"),
        event.get("message_id"),
        command.name if command is not None else "direct-code",
    )

    sender = event.get("sender") or {}
    display_name = str(sender.get("card") or sender.get("nickname") or event.get("user_id") or "群友")
    group_message = GroupMessage(
        group_id=int(event["group_id"]),
        user_id=int(event.get("user_id") or 0),
        sender_name=display_name,
        message_id=int(event["message_id"]) if event.get("message_id") is not None else None,
        message=message,
    )
    thread = threading.Thread(target=callback, args=(group_message,), daemon=True)
    thread.start()
