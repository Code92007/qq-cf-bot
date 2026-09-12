import io
import json
import tempfile
import unittest
from email.message import Message
from pathlib import Path
from unittest.mock import patch

from qq_cf_bot.config import Config
from qq_cf_bot.core import ChallengeService
from qq_cf_bot.models import CFProblem
from qq_cf_bot.webapp import WebApplication, _safe_statement_html


class _Handler:
    def __init__(self, payload=None, cookie="", csrf=""):
        body = json.dumps(payload or {}).encode("utf-8")
        self.headers = Message()
        self.headers["Content-Length"] = str(len(body))
        if cookie:
            self.headers["Cookie"] = cookie
        if csrf:
            self.headers["X-CSRF-Token"] = csrf
        self.rfile = io.BytesIO(body)
        self.wfile = io.BytesIO()
        self.status = None
        self.response_headers = []

    def send_response(self, status):
        self.status = status

    def send_header(self, name, value):
        self.response_headers.append((name, value))

    def end_headers(self):
        pass

    def json(self):
        return json.loads(self.wfile.getvalue().decode("utf-8"))

    def header(self, name):
        return next((value for key, value in self.response_headers if key.lower() == name.lower()), "")


class WebApplicationTest(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        env = {
            "BOT_DATA_DIR": self.tempdir.name,
            "WEB_COOKIE_SECURE": "false",
            "CF_SUBMIT_ENABLED": "false",
            "JUDGE_ENABLED": "false",
        }
        with patch.dict("os.environ", env, clear=True):
            config = Config.from_env()
        self.app = WebApplication(config, ChallengeService(config))

    def tearDown(self):
        self.tempdir.cleanup()

    def test_register_creates_session_and_state(self):
        register = _Handler({"username": "alice", "displayName": "Alice", "password": "password123"})

        self.assertTrue(self.app.handle_post(register, "/api/auth/register"))

        self.assertEqual(register.status, 201)
        self.assertTrue(register.json()["state"]["authenticated"])
        self.assertEqual(register.json()["state"]["user"]["displayName"], "Alice")
        self.assertEqual(register.json()["state"]["capabilities"]["codeJudgeStatus"]["state"], "disabled")
        cookie = register.header("Set-Cookie").split(";", 1)[0]

        state = _Handler(cookie=cookie)
        self.assertTrue(self.app.handle_get(state, "/api/state"))
        self.assertEqual(state.status, 200)
        self.assertEqual(state.json()["user"]["username"], "alice")

    def test_mutation_requires_csrf(self):
        register = _Handler({"username": "alice", "displayName": "Alice", "password": "password123"})
        self.app.handle_post(register, "/api/auth/register")
        cookie = register.header("Set-Cookie").split(";", 1)[0]

        logout = _Handler(cookie=cookie)
        self.app.handle_post(logout, "/api/auth/logout")

        self.assertEqual(logout.status, 403)
        self.assertEqual(logout.json()["error"], "invalid_csrf")

    def test_password_is_not_stored_in_plain_text(self):
        register = _Handler({"username": "alice", "displayName": "Alice", "password": "password123"})
        self.app.handle_post(register, "/api/auth/register")

        user = self.app.service.store.get_web_user_by_username("alice")
        self.assertNotEqual(user["password_hash"], "password123")
        self.assertTrue(user["password_hash"].startswith("pbkdf2_sha256$"))

    def test_statement_html_removes_active_content(self):
        result = _safe_statement_html(
            '<script>alert(1)</script><p onclick="alert(2)">安全文本</p><a href="javascript:alert(3)">链接</a>',
            "https://example.com/problem",
        )

        self.assertNotIn("script", result.lower())
        self.assertNotIn("onclick", result.lower())
        self.assertNotIn("javascript:", result.lower())
        self.assertIn("安全文本", result)

    def test_ac_records_requires_login_and_returns_breakdown(self):
        unauthorized = _Handler()
        self.assertTrue(self.app.handle_get(unauthorized, "/api/ac-records"))
        self.assertEqual(unauthorized.status, 401)

        register = _Handler({"username": "alice", "displayName": "Alice", "password": "password123"})
        self.app.handle_post(register, "/api/auth/register")
        response = register.json()
        user_id = response["state"]["user"]["id"]
        cookie = register.header("Set-Cookie").split(";", 1)[0]
        easy = CFProblem(1, "A", "Easy", 1200)
        hard = CFProblem(2, "B", "Hard", 2400)
        for problem in (easy, hard):
            self.app.service.store.mark_sent(-1, problem)
            self.app.service.store.record_submission(-1, user_id, "Alice", problem, "做法", True, "通过")

        records = _Handler(cookie=cookie)
        self.assertTrue(self.app.handle_get(records, "/api/ac-records"))

        self.assertEqual(records.status, 200)
        payload = records.json()
        self.assertEqual(payload["total"], 2)
        self.assertEqual(payload["ratingBreakdown"], [{"rating": 2400, "count": 1}, {"rating": 1200, "count": 1}])
        self.assertEqual([item["cfId"] for item in payload["history"]], ["2B", "1A"])


if __name__ == "__main__":
    unittest.main()
