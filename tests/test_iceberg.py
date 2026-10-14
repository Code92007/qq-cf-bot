import io
import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlparse

from qq_cf_bot.config import Config
from qq_cf_bot.core import ChallengeService
from qq_cf_bot.webapp import WebApplication


class StaticHandler:
    def __init__(self):
        self.wfile = io.BytesIO()
        self.headers = {}
        self.status = None

    def send_response(self, status):
        self.status = status

    def send_header(self, name, value):
        self.headers[name] = value

    def end_headers(self):
        pass


class IcebergTest(unittest.TestCase):
    def test_catalog_references_and_reading_links_are_valid(self):
        path = Path(__file__).parents[1] / "src/qq_cf_bot/web/iceberg-data.json"
        data = json.loads(path.read_text())
        topics = data["topics"]
        categories = {item["id"] for item in data["categories"]}
        tiers = {item["id"] for item in data["tiers"]}
        self.assertEqual(tiers, set(range(1, 9)))
        self.assertEqual(len({topic["id"] for topic in topics}), len(topics))
        self.assertEqual(len({topic["title"] for topic in topics}), len(topics))
        self.assertGreaterEqual(len(topics), 200)
        self.assertEqual({topic["tier"] for topic in topics}, tiers)
        self.assertEqual({topic["category"] for topic in topics}, categories)
        sources = {
            "OI Wiki": "oi-wiki.org", "cp-algorithms": "cp-algorithms.com",
            "KACTL": "github.com", "noshi91 Library": "noshi91.github.io",
            "USACO Guide": "usaco.guide", "原始论文": "arxiv.org",
            "Darrell Whitley": "www.cs.colostate.edu",
            "codeforces-go": "github.com", "Codeforces": "codeforces.com",
            "Princeton Algorithms": "algs4.cs.princeton.edu", "OGDF": "ogdf.github.io",
            "MIT 论文库": "dspace.mit.edu", "CGAL": "doc.cgal.org",
            "SageMath": "doc.sagemath.org",
        }
        for topic in topics:
            with self.subTest(topic=topic["id"]):
                self.assertRegex(topic["id"], r"^[a-z0-9-]+$")
                self.assertIn(topic["category"], categories)
                self.assertIn(topic["tier"], tiers)
                self.assertIn(topic["difficulty"], range(1, 6))
                self.assertIn(topic["popularity"], range(1, 6))
                self.assertTrue(topic["summary"].strip())
                self.assertIsInstance(topic["aliases"], str)
                parsed = urlparse(topic["url"])
                self.assertEqual(parsed.scheme, "https")
                self.assertEqual(parsed.hostname, sources[topic["source"]])
                self.assertNotEqual(parsed.path, "/")
                self.assertIn(topic["kind"], {"article", "implementation"})
                references = topic.get("references", [])
                self.assertIsInstance(references, list)
                urls = [topic["url"]] + [ref["url"] for ref in references]
                self.assertEqual(len(urls), len(set(urls)))
                for ref in references:
                    self.assertTrue(ref["title"].strip())
                    self.assertIn(ref["kind"], {"article", "implementation"})
                    self.assertEqual(urlparse(ref["url"]).scheme, "https")
                    self.assertIn(urlparse(ref["url"]).hostname, sources.values())
                for url in urls:
                    if "/Zhonghe-zhao/codeforces-go/" in url:
                        self.assertRegex(url, r"^https://github\.com/Zhonghe-zhao/codeforces-go/blob/[0-9a-f]{40}/copypasta/[a-z0-9_]+\.go#L[1-9][0-9]*$")

    def test_public_routes_and_assets_without_a_session(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict("os.environ", {"BOT_DATA_DIR": directory, "CF_SUBMIT_ENABLED": "false", "JUDGE_ENABLED": "false"}, clear=True):
                config = Config.from_env()
            app = WebApplication(config, ChallengeService(config))
            for path, content_type in (
                ("/iceberg", "text/html"), ("/iceberg/", "text/html"),
                ("/iceberg.js", "text/javascript"), ("/iceberg.css", "text/css"),
                ("/iceberg-data.json", "application/json"),
            ):
                with self.subTest(path=path):
                    handler = StaticHandler()
                    self.assertTrue(app.handle_get(handler, path))
                    self.assertEqual(handler.status, 200)
                    self.assertTrue(handler.headers["Content-Type"].startswith(content_type))
                    self.assertTrue(handler.wfile.getvalue())
                    if path.endswith(".json"):
                        self.assertGreater(len(json.loads(handler.wfile.getvalue())["topics"]), 0)
            app.config = replace(config, web_enabled=False)
            self.assertFalse(app.handle_get(StaticHandler(), "/iceberg"))


if __name__ == "__main__":
    unittest.main()
