import tempfile
import unittest
from pathlib import Path

from qq_cf_bot.onebot import OneBotClient


class OneBotClientTest(unittest.TestCase):
    def test_base64_image_file_value(self):
        with tempfile.TemporaryDirectory() as tmp:
            image = Path(tmp) / "x.png"
            image.write_bytes(b"abc")
            value = OneBotClient("http://127.0.0.1:3000")._image_file_value(image)
            self.assertEqual(value, "base64://YWJj")


if __name__ == "__main__":
    unittest.main()
