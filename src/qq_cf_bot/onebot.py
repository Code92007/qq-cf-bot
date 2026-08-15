from __future__ import annotations

import base64
import json
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


class OneBotClient:
    def __init__(
        self,
        base_url: str,
        access_token: str = "",
        image_mode: str = "base64",
        self_id: Optional[int] = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.access_token = access_token
        self.image_mode = image_mode
        self.self_id = self_id

    def send_group_text(self, group_id: int, text: str) -> None:
        self.send_group_msg(group_id, [{"type": "text", "data": {"text": text}}])

    def send_group_image(self, group_id: int, image: Path) -> None:
        self.send_group_msg(group_id, [{"type": "image", "data": {"file": self._image_file_value(image)}}])

    def send_group_problem(self, group_id: int, text: str, images: Iterable[Path]) -> None:
        message: List[Dict[str, Any]] = [{"type": "text", "data": {"text": text.rstrip() + "\n"}}]
        for image in images:
            message.append({"type": "image", "data": {"file": self._image_file_value(image)}})
        self.send_group_msg(group_id, message)

    def send_group_forward_images(
        self,
        group_id: int,
        images: Iterable[Path],
        sender_name: str = "题面",
        sender_uin: str = "10000",
    ) -> None:
        image_list = list(images)
        if not image_list:
            return
        try:
            self.send_group_forward_images_via_self(group_id, image_list)
            return
        except Exception:
            self.send_group_forward_custom_images(group_id, image_list, sender_name, sender_uin)

    def send_group_forward_images_via_self(self, group_id: int, images: Iterable[Path]) -> None:
        image_list = list(images)
        if not image_list:
            return
        message: List[Dict[str, Any]] = [{"type": "text", "data": {"text": "题面\n"}}]
        for image in image_list:
            message.append({"type": "image", "data": {"file": self._image_file_value(image)}})
        result = self.send_private_msg(self.get_login_user_id(), message)
        message_id = _message_id_from_result(result)
        if message_id is None:
            raise RuntimeError(f"OneBot send_private_msg did not return message_id: {result!r}")
        self.send_group_forward_message_ids(group_id, [message_id])

    def send_group_forward_custom_images(
        self,
        group_id: int,
        images: Iterable[Path],
        sender_name: str = "题面",
        sender_uin: str = "10000",
    ) -> None:
        nodes: List[Dict[str, Any]] = []
        for index, image in enumerate(images, start=1):
            nodes.append(
                {
                    "type": "node",
                    "data": {
                        "name": sender_name,
                        "uin": sender_uin,
                        "content": [
                            {"type": "text", "data": {"text": f"题面 #{index}\n"}},
                            {"type": "image", "data": {"file": self._image_file_value(image)}},
                        ],
                    },
                }
            )
        if not nodes:
            return
        self._post("/send_group_forward_msg", {"group_id": group_id, "messages": nodes})

    def send_group_forward_message_ids(self, group_id: int, message_ids: Iterable[int]) -> None:
        nodes = [{"type": "node", "data": {"id": str(message_id)}} for message_id in message_ids]
        if not nodes:
            return
        self._post("/send_group_forward_msg", {"group_id": group_id, "messages": nodes})

    def send_private_msg(self, user_id: int, message: Any) -> dict:
        payload = {"user_id": user_id, "message": message, "auto_escape": False}
        return self._post("/send_private_msg", payload)

    def send_group_msg(self, group_id: int, message: Any) -> None:
        payload = {"group_id": group_id, "message": message, "auto_escape": False}
        self._post("/send_group_msg", payload)

    def get_login_user_id(self) -> int:
        if self.self_id is not None:
            return self.self_id
        result = self._post("/get_login_info", {})
        data = result.get("data") if isinstance(result.get("data"), dict) else {}
        raw_user_id = data.get("user_id") or result.get("user_id")
        if raw_user_id is None:
            raise RuntimeError(f"OneBot get_login_info did not return user_id: {result!r}")
        self.self_id = int(raw_user_id)
        return self.self_id

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


def _message_id_from_result(result: dict) -> Optional[int]:
    containers = []
    data = result.get("data")
    if isinstance(data, dict):
        containers.append(data)
    containers.append(result)
    for container in containers:
        for key in ("message_id", "messageId", "id"):
            value = container.get(key)
            if value is None:
                continue
            try:
                return int(value)
            except (TypeError, ValueError):
                continue
    return None
