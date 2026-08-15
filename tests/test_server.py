import io
import unittest
from email.message import Message

from qq_cf_bot.server import _read_request_body


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


if __name__ == "__main__":
    unittest.main()
