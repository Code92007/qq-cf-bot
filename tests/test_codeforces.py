import io
import json
import unittest
from unittest.mock import patch

from qq_cf_bot.codeforces import _fetch_json_from_codeforces_variants


class _FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.close()


class CodeforcesClientTest(unittest.TestCase):
    def test_fetch_json_falls_back_when_primary_is_non_ok(self):
        seen_urls = []

        def fake_urlopen(request, timeout):
            del timeout
            seen_urls.append(request.full_url)
            status = "FAILED" if request.full_url.startswith("https://codeforces.com/") else "OK"
            return _FakeResponse(json.dumps({"status": status, "result": []}).encode("utf-8"))

        with patch("qq_cf_bot.codeforces.urllib.request.urlopen", side_effect=fake_urlopen):
            payload = _fetch_json_from_codeforces_variants(
                "/api/problemset.problems",
                ("https://codeforces.com", "https://m1.codeforces.com"),
                timeout_seconds=20,
            )

        self.assertEqual(payload["status"], "OK")
        self.assertEqual(
            seen_urls,
            [
                "https://codeforces.com/api/problemset.problems",
                "https://m1.codeforces.com/api/problemset.problems",
            ],
        )


if __name__ == "__main__":
    unittest.main()
