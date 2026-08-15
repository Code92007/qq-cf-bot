from __future__ import annotations

import base64
import json
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, Iterable, List


class OneBotClient:
    def __init__(self, base_url: str, access_token: str = "", image_mode: str = "base64") -> None:
        self.base_url = base_url.rstrip("/")
        self.access_token = access_token
        self.image_mode = image_mode

    def send_group_text(self, group_id: int, text: str) -> None:
        self.send_group_msg(group_id, [{"type": "text", "data": {"text": text}}])

    def send_group_image(self, group_id: int, image: Path) -> None:
        self.send_group_msg(group_id, [{"type": "image", "data": {"file": self._image_file_value(image)}}])

    def send_group_problem(self, group_id: int, text: str, images: Iterable[Path]) -> None:
        message: List[Dict[str, Any]] = [{"type": "text", "data": {"text": text.rstrip() + "\n"}}]
        for image in images:
            message.append({"type": "image", "data": {"file": self._image_file_value(image)}})
        self.send_group_msg(group_id, message)

    def send_group_msg(self, group_id: int, message: Any) -> None:
        payload = {"group_id": group_id, "message": message, "auto_escape": False}
        self._post("/send_group_msg", payload)

    def _post(self, path: str, payload: dict) -> dict:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "qq-cf-bot/0.1",
        }
        if self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"
        request = urllib.request.Request(self.base_url + path, data=data, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                body = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"OneBot API returned HTTP {exc.code}: {body}") from exc

        if not body:
            return {}
        result = json.loads(body)
        status = result.get("status")
        if status and status != "ok":
            raise RuntimeError(f"OneBot API returned non-ok status: {result!r}")
        return result

    def _image_file_value(self, image: Path) -> str:
        if self.image_mode == "file_uri":
            return image.resolve().as_uri()
        data = base64.b64encode(image.read_bytes()).decode("ascii")
        return f"base64://{data}"
