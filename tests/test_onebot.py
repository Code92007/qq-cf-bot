import tempfile
import unittest
from pathlib import Path

from qq_cf_bot.onebot import OneBotClient, _message_id_from_result


class OneBotClientTest(unittest.TestCase):
    def test_base64_image_file_value(self):
        with tempfile.TemporaryDirectory() as tmp:
            image = Path(tmp) / "x.png"
            image.write_bytes(b"abc")
            value = OneBotClient("http://127.0.0.1:3000")._image_file_value(image)
            self.assertEqual(value, "base64://YWJj")

    def test_send_group_forward_images_uses_self_private_message(self):
        with tempfile.TemporaryDirectory() as tmp:
            image = Path(tmp) / "x.png"
            image.write_bytes(b"abc")
            client = _FakeOneBotClient()

            client.send_group_forward_images(123, [image])

            self.assertEqual(client.posts[0], ("/get_login_info", {}))
            self.assertEqual(client.posts[1][0], "/send_private_msg")
            self.assertEqual(client.posts[1][1]["user_id"], 9988)
            self.assertEqual(
                client.posts[2],
                (
                    "/send_group_forward_msg",
                    {"group_id": 123, "messages": [{"type": "node", "data": {"id": "456"}}]},
                ),
            )

    def test_send_group_forward_images_falls_back_to_custom_forward(self):
        with tempfile.TemporaryDirectory() as tmp:
            image = Path(tmp) / "x.png"
            image.write_bytes(b"abc")
            client = _PrivateMessageFailsClient()

            client.send_group_forward_images(123, [image])

            self.assertEqual(client.posts[-1][0], "/send_group_forward_msg")
            node = client.posts[-1][1]["messages"][0]
            self.assertEqual(node["type"], "node")
            self.assertEqual(node["data"]["content"][0]["type"], "text")
            self.assertEqual(node["data"]["content"][1]["type"], "image")

    def test_extracts_message_id_from_common_result_shapes(self):
        self.assertEqual(_message_id_from_result({"data": {"message_id": "123"}}), 123)
        self.assertEqual(_message_id_from_result({"messageId": 124}), 124)
        self.assertIsNone(_message_id_from_result({"data": {}}))


class _FakeOneBotClient(OneBotClient):
    def __init__(self) -> None:
        super().__init__("http://127.0.0.1:3000")
        self.posts = []

    def _post(self, path: str, payload: dict) -> dict:
        self.posts.append((path, payload))
        if path == "/get_login_info":
            return {"status": "ok", "data": {"user_id": 9988}}
        if path == "/send_private_msg":
            return {"status": "ok", "data": {"message_id": 456}}
        return {"status": "ok", "data": {}}


class _PrivateMessageFailsClient(_FakeOneBotClient):
    def _post(self, path: str, payload: dict) -> dict:
        if path == "/send_private_msg":
            raise RuntimeError("private chat is unavailable")
        return super()._post(path, payload)


if __name__ == "__main__":
    unittest.main()
