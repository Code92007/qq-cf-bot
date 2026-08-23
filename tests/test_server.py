import io
import queue
import unittest
from email.message import Message

from qq_cf_bot.server import _handle_event, _is_authorized, _read_request_body


class FakeHandler:
    def __init__(self, headers: Message, body: bytes):
        self.headers = headers
        self.rfile = io.BytesIO(body)


class ServerTest(unittest.TestCase):
    def test_read_content_length_body(self):
        headers = Message()
        headers["Content-Length"] = "7"
        handler = FakeHandler(headers, b'{"x":1}')
        self.assertEqual(_read_request_body(handler), b'{"x":1}')

    def test_read_chunked_body(self):
        headers = Message()
        headers["Transfer-Encoding"] = "chunked"
        body = b'4\r\n{"x"\r\n3\r\n:1}\r\n0\r\n\r\n'
        handler = FakeHandler(headers, body)
        self.assertEqual(_read_request_body(handler), b'{"x":1}')

    def test_at_only_group_message_becomes_help(self):
        messages = queue.Queue()
        _handle_event(
            {
                "post_type": "message",
                "message_type": "group",
                "self_id": 3849894908,
                "group_id": 1094199203,
                "user_id": 1072805307,
                "message_id": 123,
                "sender": {"nickname": "tester"},
                "message": [{"type": "at", "data": {"qq": "3849894908"}}],
            },
            messages.put,
        )

        group_message = messages.get(timeout=1)
        self.assertEqual(group_message.message, "/help")

    def test_event_auth_accepts_bearer_token(self):
        headers = Message()
        headers["Authorization"] = "Bearer event-secret"

        self.assertTrue(_is_authorized(headers, "", "event-secret"))

    def test_event_auth_rejects_wrong_token(self):
        headers = Message()
        headers["Authorization"] = "Bearer wrong"

        self.assertFalse(_is_authorized(headers, "", "event-secret"))

    def test_event_auth_accepts_query_token(self):
        headers = Message()

        self.assertTrue(_is_authorized(headers, "access_token=event-secret", "event-secret"))


if __name__ == "__main__":
    unittest.main()
