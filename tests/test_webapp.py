import io
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from email.message import Message
from pathlib import Path
from unittest.mock import patch

from qq_cf_bot.config import Config
from qq_cf_bot.core import ChallengeService, SubmissionOutcome
from qq_cf_bot.models import CFContest, CFProblem, PreparedProblem, ProblemStatement, RatingRange
from qq_cf_bot.webapp import (
    WebApplication,
    _assistance_settings,
    _resolved_hint_control,
    _compressed_hints,
    _assistance_unlock_seconds,
    _giveup_minutes,
    _safe_statement_html,
)


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

    def test_giveup_minutes_are_bounded(self):
        self.assertEqual(_giveup_minutes(None), 90)
        self.assertEqual(_giveup_minutes("45"), 45)
        with self.assertRaises(ValueError):
            _giveup_minutes(19)
        with self.assertRaises(ValueError):
            _giveup_minutes(241)

    def test_dynamic_hint_count_and_compression(self):
        settings = _assistance_settings({})
        self.assertEqual(settings["hint_count"], 0)
        for rating, expected in [(800, 2), (1200, 2), (1400, 3), (1800, 3),
                                 (2000, 4), (2400, 4), (2600, 5)]:
            control = _resolved_hint_control(settings, rating)
            self.assertEqual(control["hint_count"], expected)
            hints = tuple(str(i) for i in range(6))
            compressed = _compressed_hints(hints, expected)
            self.assertEqual(len(compressed), expected)
            self.assertEqual("\n".join(compressed), "\n".join(hints))
        self.assertEqual(_resolved_hint_control({"hint_count": 1}, 2600)["hint_count"], 1)

    def test_assistance_settings_are_configurable_and_bounded(self):
        settings = _assistance_settings(
            {
                "tagUnlockMinutes": 3,
                "firstHintMinutes": 7,
                "hintIntervalMinutes": 4,
                "hintCount": 3,
            }
        )

        self.assertEqual(
            _assistance_unlock_seconds(settings),
            (180, 420, 660, 900),
        )
        with self.assertRaises(ValueError):
            _assistance_settings({"hintCount": 7})
        with self.assertRaises(ValueError):
            _assistance_settings({"tagUnlockMinutes": -1})

    def test_progressive_assistance_unlocks_only_after_server_deadline(self):
        register = _Handler({"username": "alice", "displayName": "Alice", "password": "password123"})
        self.app.handle_post(register, "/api/auth/register")
        response = register.json()
        user_id = response["state"]["user"]["id"]
        cookie = register.header("Set-Cookie").split(";", 1)[0]
        csrf = response["state"]["csrfToken"]
        scope_id = -(1_000_000_000_000 + user_id)
        problem = CFProblem(1, "A", "Theatre Square", 1000, ("math", "implementation"))
        statement = ProblemStatement("CF1A", "剧院广场", "description", "input", "output", [])
        self.app.service.store.set_active_problem(scope_id, problem, statement, [])
        started_at = (datetime.now(timezone.utc) - timedelta(minutes=21)).isoformat()
        giveup_at = (datetime.now(timezone.utc) + timedelta(minutes=30)).isoformat()
        self.app.service.store.set_web_challenge_control(
            scope_id,
            user_id,
            problem.cf_id,
            started_at,
            giveup_at=giveup_at,
            giveup_minutes=51,
        )

        current = _Handler(cookie=cookie)
        self.app.handle_get(current, "/api/state")
        assistance = current.json()["active"]["assistance"]
        self.assertEqual(assistance["steps"][0]["waitSeconds"], 0)
        self.assertNotIn("tags", assistance["steps"][0])
        self.assertEqual(assistance["steps"][1]["waitSeconds"], 0)

        tags = _Handler({"step": 0, "contest": False}, cookie=cookie, csrf=csrf)
        self.app.handle_post(tags, "/api/challenges/hints/reveal")
        self.assertEqual(tags.status, 200)
        self.assertEqual(tags.json()["state"]["active"]["assistance"]["steps"][0]["tags"], ["math", "implementation"])

        generated = tuple(f"渐进提示 {index}" for index in range(1, 7))
        self.app.service.store.set_problem_hints(problem.cf_id, generated)
        with patch.object(self.app.service.solution_bank, "hints_for", return_value=generated):
            hint = _Handler({"step": 1, "contest": False}, cookie=cookie, csrf=csrf)
            self.app.handle_post(hint, "/api/challenges/hints/reveal")
        self.assertEqual(hint.status, 200)
        self.assertEqual(
            hint.json()["state"]["active"]["assistance"]["steps"][1]["content"],
            "渐进提示 1",
        )

    def test_progressive_assistance_rejects_locked_hint(self):
        register = _Handler({"username": "alice", "displayName": "Alice", "password": "password123"})
        self.app.handle_post(register, "/api/auth/register")
        response = register.json()
        user_id = response["state"]["user"]["id"]
        cookie = register.header("Set-Cookie").split(";", 1)[0]
        csrf = response["state"]["csrfToken"]
        scope_id = -(1_000_000_000_000 + user_id)
        problem = CFProblem(1, "A", "Theatre Square", 1000, ("math",))
        statement = ProblemStatement("CF1A", "剧院广场", "description", "input", "output", [])
        self.app.service.store.set_active_problem(scope_id, problem, statement, [])
        active = self.app.service.store.get_active_problem(scope_id)
        self.app.service.store.set_web_challenge_control(
            scope_id, user_id, problem.cf_id, active.created_at
        )

        hint = _Handler({"step": 1, "contest": False}, cookie=cookie, csrf=csrf)
        self.app.handle_post(hint, "/api/challenges/hints/reveal")

        self.assertEqual(hint.status, 409)
        self.assertEqual(hint.json()["error"], "hint_locked")

    def test_progressive_assistance_can_be_revealed_early(self):
        register = _Handler({"username": "alice", "displayName": "Alice", "password": "password123"})
        self.app.handle_post(register, "/api/auth/register")
        response = register.json()
        user_id = response["state"]["user"]["id"]
        cookie = register.header("Set-Cookie").split(";", 1)[0]
        csrf = response["state"]["csrfToken"]
        scope_id = -(1_000_000_000_000 + user_id)
        problem = CFProblem(1, "A", "Theatre Square", 1000, ("math",))
        statement = ProblemStatement("CF1A", "剧院广场", "description", "input", "output", [])
        self.app.service.store.set_active_problem(scope_id, problem, statement, [])
        active = self.app.service.store.get_active_problem(scope_id)
        self.app.service.store.set_web_challenge_control(
            scope_id,
            user_id,
            problem.cf_id,
            active.created_at,
            first_hint_minutes=120,
            hint_count=2,
        )
        generated = tuple(f"渐进提示 {index}" for index in range(1, 7))
        self.app.service.store.set_problem_hints(problem.cf_id, generated)

        with patch.object(self.app.service.solution_bank, "hints_for", return_value=generated):
            hint = _Handler({"step": 1, "contest": False, "early": True}, cookie=cookie, csrf=csrf)
            self.app.handle_post(hint, "/api/challenges/hints/reveal")

        self.assertEqual(hint.status, 200)
        assistance = hint.json()["state"]["active"]["assistance"]
        self.assertEqual(len(assistance["steps"]), 3)
        self.assertTrue(assistance["steps"][1]["revealed"])
        self.assertEqual(assistance["steps"][1]["content"], "渐进提示 1\n渐进提示 2\n渐进提示 3")

    def test_state_forces_giveup_after_voluntary_deadline(self):
        register = _Handler({"username": "alice", "displayName": "Alice", "password": "password123"})
        self.app.handle_post(register, "/api/auth/register")
        response = register.json()
        user_id = response["state"]["user"]["id"]
        cookie = register.header("Set-Cookie").split(";", 1)[0]
        scope_id = -(1_000_000_000_000 + user_id)
        problem = CFProblem(1, "A", "Theatre Square", 1000, ("math",))
        statement = ProblemStatement("CF1A", "剧院广场", "description", "input", "output", [])
        self.app.service.store.set_active_problem(scope_id, problem, statement, [])
        active = self.app.service.store.get_active_problem(scope_id)
        self.app.service.store.set_web_challenge_control(
            scope_id,
            user_id,
            problem.cf_id,
            active.created_at,
            giveup_at=(datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat(),
            giveup_minutes=20,
        )

        current = _Handler(cookie=cookie)
        self.app.handle_get(current, "/api/state")

        payload = current.json()
        self.assertIsNone(payload["active"])
        self.assertEqual(payload["forcedGiveup"]["cfId"], "1A")
        self.assertIsNone(self.app.service.store.get_active_problem(scope_id))

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

    def test_share_challenge_accepts_problem_url_and_rejects_invalid_id(self):
        register = _Handler({"username": "alice", "displayName": "Alice", "password": "password123"})
        self.app.handle_post(register, "/api/auth/register")
        response = register.json()
        cookie = register.header("Set-Cookie").split(";", 1)[0]
        csrf = response["state"]["csrfToken"]

        with patch.object(self.app.service, "issue_specific_problem") as issue:
            share = _Handler(
                {"problemId": "https://codeforces.com/contest/1704/problem/f"},
                cookie=cookie,
                csrf=csrf,
            )
            self.assertTrue(self.app.handle_post(share, "/api/challenges/share"))

        self.assertEqual(share.status, 200)
        scope_id = -(1_000_000_000_000 + response["state"]["user"]["id"])
        issue.assert_called_once_with(scope_id, 1704, "F")

        invalid = _Handler({"problemId": "1704"}, cookie=cookie, csrf=csrf)
        self.assertTrue(self.app.handle_post(invalid, "/api/challenges/share"))
        self.assertEqual(invalid.status, 400)
        self.assertEqual(invalid.json()["error"], "invalid_request")

    def test_contest_session_keeps_problem_after_oral_ac_and_records_timeline(self):
        register = _Handler({"username": "alice", "displayName": "Alice", "password": "password123"})
        self.app.handle_post(register, "/api/auth/register")
        response = register.json()
        cookie = register.header("Set-Cookie").split(";", 1)[0]
        csrf = response["state"]["csrfToken"]
        contest = CFContest(2000, "Codeforces Round 999 (Div. 2)", "FINISHED", 7200)
        problems = [CFProblem(2000, "A", "First", 800), CFProblem(2000, "B", "Second", 1200)]
        statement = ProblemStatement("CF2000A", "First", "description", "input", "output", [])
        prepared = PreparedProblem(problems[0], statement, [], RatingRange(800, 800), "now")

        with (
            patch.object(self.app.service.cf, "fetch_contest", return_value=(contest, problems)),
            patch.object(self.app.service, "prepare_specific_problem", return_value=prepared),
        ):
            start = _Handler({"category": "div2", "contestId": "2000"}, cookie=cookie, csrf=csrf)
            self.assertTrue(self.app.handle_post(start, "/api/contest-sessions"))

        self.assertEqual(start.status, 201)
        started_state = start.json()["state"]
        self.assertIsNone(started_state["active"])
        self.assertEqual(started_state["contestSession"]["currentCfId"], "2000A")
        self.assertEqual(len(started_state["contestSession"]["problems"]), 2)
        scope_id = -(2_000_000_000_000 + response["state"]["user"]["id"])
        active = self.app.service.get_active_problem(scope_id)

        with patch.object(
            self.app.service,
            "submit_solution",
            return_value=SubmissionOutcome(active=active, accepted=True, reason="思路正确。", settled=False),
        ) as submit:
            oral = _Handler({"solution": "做法"}, cookie=cookie, csrf=csrf)
            self.assertTrue(self.app.handle_post(oral, "/api/contest-sessions/oral"))

        submit.assert_called_once()
        self.assertFalse(submit.call_args.kwargs["settle"])
        oral_state = oral.json()["state"]["contestSession"]
        self.assertIsNotNone(oral_state["problems"][0]["oralAcceptedAt"])
        self.assertIsNotNone(self.app.service.get_active_problem(scope_id))

        end = _Handler({}, cookie=cookie, csrf=csrf)
        self.assertTrue(self.app.handle_post(end, "/api/contest-sessions/end"))
        self.assertEqual(end.json()["ended"]["status"], "ended")
        self.assertIsNone(end.json()["state"]["contestSession"])
        self.assertEqual(end.json()["state"]["lastContestSession"]["contestId"], 2000)
        self.assertIsNone(self.app.service.get_active_problem(scope_id))


if __name__ == "__main__":
    unittest.main()
