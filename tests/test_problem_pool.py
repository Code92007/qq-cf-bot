import io
import json
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from email.message import Message
from unittest.mock import patch

from qq_cf_bot.config import Config
from qq_cf_bot.core import ChallengeError, ChallengeService
from qq_cf_bot.models import CFProblem, PreparedProblem, ProblemStatement, RatingRange
from qq_cf_bot.problem_pool import normalize_problem
from qq_cf_bot.webapp import WebApplication


class Handler:
    def __init__(self, payload=None, path="", cookie="", csrf=""):
        raw = json.dumps(payload or {}).encode()
        self.path = path
        self.headers = Message()
        self.headers["Content-Length"] = str(len(raw))
        if cookie:
            self.headers["Cookie"] = cookie
        if csrf:
            self.headers["X-CSRF-Token"] = csrf
        self.rfile, self.wfile = io.BytesIO(raw), io.BytesIO()
        self.status, self.response_headers = None, {}

    def send_response(self, status):
        self.status = status

    def send_header(self, name, value):
        self.response_headers[name] = value

    def end_headers(self):
        pass

    def json(self):
        return json.loads(self.wfile.getvalue())


class ProblemIdentityTest(unittest.TestCase):
    def test_mirrors_urls_and_case_deduplicate(self):
        for value in ("cf1704f", "https://codeforces.com/contest/1704/problem/F?locale=zh",
                      "https://codeforces.com/problemset/problem/1704/F/", "https://www.luogu.com.cn/problem/CF1704F",
                      "https://vjudge.net/problem/CodeForces-1704F", "vjudge:CodeForces-1704f"):
            with self.subTest(value=value):
                self.assertEqual(normalize_problem(value)["key"], "codeforces:1704F")
        self.assertEqual(normalize_problem("105789a")["url"], "https://codeforces.com/gym/105789/problem/A")
        self.assertEqual(normalize_problem("Gym-105789A", "vjudge")["key"], "codeforces:105789A")

    def test_multiple_oj_identities(self):
        cases = [
            ("p1001", "auto", "luogu:P1001"),
            ("https://qoj.ac/problem/001234?locale=zh", "auto", "qoj:1234"),
            ("001234", "qoj", "qoj:1234"),
            ("abc350_f", "auto", "atcoder:ABC350_F"),
            ("https://atcoder.jp/contests/abc350/tasks/abc350_f", "auto", "atcoder:ABC350_F"),
            ("https://ac.nowcoder.com/acm/contest/123/A", "auto", "nowcoder:123:A"),
            ("https://ac.nowcoder.com/acm/problem/220443", "auto", "nowcoder:220443"),
            ("HDU-1000", "auto", "vjudge:HDU-1000"),
            ("https://vjudge.net/problem/QOJ-1234", "auto", "qoj:1234"),
        ]
        for value, platform, key in cases:
            with self.subTest(value=value):
                self.assertEqual(normalize_problem(value, platform)["key"], key)
        unusual = "https://atcoder.jp/contests/code-festival-2016-quala/tasks/codefestival_2016_qualA_a"
        self.assertEqual(normalize_problem(unusual)["url"], unusual.lower())
        self.assertEqual(normalize_problem("AT_abc350_f")["url"], "https://www.luogu.com.cn/problem/AT_abc350_f")

    def test_invalid_and_lookalike_links_are_rejected(self):
        for value in ("1234", "https://codeforces.com.evil.test/contest/1704/problem/F",
                      "https://evil.luogu.com.cn/problem/P1001", "javascript:alert(1)",
                      "https://codeforces.com@evil.test/contest/1704/problem/F",
                      "https://qoj.ac:443/problem/1", "https://qoj.ac/problem/0", "https://codeforces.com/contest/123"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                normalize_problem(value)


class ProblemPoolTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        with patch.dict("os.environ", {"BOT_DATA_DIR": self.tmp.name, "CF_SUBMIT_ENABLED": "false", "JUDGE_ENABLED": "false"}, clear=True):
            config = Config.from_env()
        self.web = WebApplication(config, ChallengeService(config))
        self.pool = self.web.pool
        self.alice = self.session("alice")
        self.bob = self.session("bob")

    def tearDown(self):
        self.tmp.cleanup()

    def session(self, name):
        user = self.web.service.store.create_web_user(name, name.title(), "unused-test-hash")
        return {"user_id": user["id"], "display_name": user["display_name"], "username": name, "csrf_token": "test-csrf"}

    def add(self, problem="1704F", **fields):
        return self.pool.post(self.alice, "problems", {"problemId": problem, **fields})["item"]

    def list(self, session=None, **filters):
        return self.pool.listing((session or self.alice)["user_id"], filters)

    def record(self, item, status, session=None):
        return self.pool.post(session or self.alice, "record", {"id": item["id"], "status": status})["item"]

    def test_shared_dedup_keeps_original_recommendation_and_personal_states(self):
        first = self.add(title="群友好题", note="试试吧", tags="思维，贪心")
        duplicate = self.pool.post(self.bob, "problems", {"problemId": "https://vjudge.net/problem/CodeForces-1704F", "note": "覆盖原文"})
        self.assertFalse(duplicate["created"])
        self.assertEqual(duplicate["item"]["id"], first["id"])
        self.assertEqual(duplicate["item"]["note"], "试试吧")
        self.assertEqual(self.list()["counts"]["all"], 1)
        self.record(first, "skipped")
        self.assertEqual(self.list()["items"][0]["status"], "skipped")
        self.assertEqual(self.list(self.bob)["items"][0]["status"], "new")
        self.assertEqual(self.pool.post(self.bob, "draw", {})["item"]["id"], first["id"])

    def test_fishing_is_private_persistent_and_excludes_drawn_skipped_and_ac(self):
        items = [self.add(problem) for problem in ("1704F", "P1001", "abc350_f")]
        self.record(items[0], "skipped")
        self.record(items[1], "ac")
        drawn = self.pool.post(self.alice, "draw", {})["item"]
        self.assertEqual(drawn["id"], items[2]["id"])
        self.assertEqual(drawn["status"], "picked")
        self.assertEqual(drawn["drawCount"], 1)
        with self.assertRaises(ChallengeError) as cm:
            self.pool.post(self.alice, "draw", {})
        self.assertEqual(cm.exception.code, "pool_empty")
        # Restarting the application does not forget records.
        self.web = WebApplication(self.web.config, self.web.service)
        self.pool = self.web.pool
        self.assertEqual(self.list()["counts"], {"all": 3, "new": 0, "picked": 1, "skipped": 1, "ac": 1})
        self.record(drawn, "new")
        redrawn = self.pool.post(self.alice, "draw", {})["item"]
        self.assertEqual(redrawn["drawCount"], 2)
        self.record(items[1], "new")
        self.assertEqual(self.list()["counts"]["ac"], 0)

    def test_filtering_applies_to_both_list_and_draw(self):
        target = self.add("1704F", title="Colouring Game", rating=2400, tags=["思维"], note="很适合口胡")
        self.add("P1001", rating=800, tags=["入门"])
        self.add("1705A", tags=["思维"])
        self.pool.post(self.bob, "problems", {"problemId": "1706A", "rating": 2400, "tags": ["思维"]})
        filters = {"platform": "codeforces", "tag": "思维", "minRating": 2000, "maxRating": 2600, "mine": "1", "q": "口胡"}
        self.assertEqual([p["id"] for p in self.list(**filters)["items"]], [target["id"]])
        self.assertEqual(self.pool.post(self.alice, "draw", {"filters": filters})["item"]["id"], target["id"])
        self.assertEqual(self.list(**filters)["available"], 0)
        self.assertEqual(self.list(self.bob, mine=True)["total"], 1)
        with self.assertRaises(ValueError):
            self.list(minRating=2400, maxRating=800)

    def test_simultaneous_draws_and_duplicate_tosses_are_atomic(self):
        self.add("1704F")
        self.add("1705A")
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(lambda _: self.pool.post(self.alice, "draw", {})["item"]["id"], range(2)))
        self.assertEqual(len(set(results)), 2)
        with ThreadPoolExecutor(max_workers=2) as executor:
            tossed = list(executor.map(lambda s: self.pool.post(s, "problems", {"problemId": "abc350_f"}), (self.alice, self.bob)))
        self.assertEqual(sum(p["created"] for p in tossed), 1)

    def test_manual_ac_is_reversible_and_does_not_change_rating(self):
        item = self.add()
        before = self.web.service.get_user_stat(self.web._actor(self.alice))
        accepted = self.record(item, "ac")
        repeated = self.record(item, "ac")
        self.assertTrue(accepted["acAt"])
        self.assertEqual(accepted["acAt"], repeated["acAt"])
        self.assertEqual(accepted["acSource"], "手动 AC")
        after = self.web.service.get_user_stat(self.web._actor(self.alice))
        self.assertEqual((before.rating, before.solved_count), (after.rating, after.solved_count))
        restored = self.record(item, "new")
        self.assertEqual(restored["acAt"], "")

    def test_existing_training_ac_including_unranked_and_vp_is_excluded(self):
        item = self.add()
        self.web.service.store.record_submission(-1, self.alice["user_id"], "Alice", CFProblem(1704, "F", "Game", 2400), "idea", True, "OK", ranked=False)
        accepted = self.list()["items"][0]
        self.assertEqual(accepted["status"], "ac")
        self.assertEqual(accepted["acSource"], "站内通过")
        self.assertTrue(accepted["importedAc"])
        with self.assertRaises(ChallengeError):
            self.record(item, "new")
        self.assertEqual(self.list(self.bob)["counts"]["new"], 1)

    def test_synced_platform_and_regional_alias_ac_are_excluded_and_reversible_upstream(self):
        regional = self.web.regionals.store
        problem = next(p for p in regional.problems.values() if any(k.startswith("qoj:") for k in p["aliases"]) and any(k.startswith("codeforces:") for k in p["aliases"]))
        qoj_key = next(k for k in problem["aliases"] if k.startswith("qoj:"))
        cf_key = next(k for k in problem["aliases"] if k.startswith("codeforces:"))
        self.add(qoj_key)
        self.add(cf_key)
        with regional.connect() as db:
            db.execute("insert into regional_evidence values (?,?,?,?,?,?,?,?)", (self.alice["user_id"], "test", "one", qoj_key, "AC", 1700000000, "qoj", "alice"))
        self.assertEqual(self.list()["counts"]["ac"], 2)
        self.assertEqual(self.list(self.bob)["counts"]["ac"], 0)
        with regional.connect() as db:
            db.execute("delete from regional_evidence")
        self.assertEqual(self.list()["counts"]["new"], 2)
        regional.attempt(self.alice["user_id"], problem["id"], "request", "oral", "idea", True, "ORAL_ACCEPTED", "correct")
        self.assertEqual(self.list()["counts"]["ac"], 2)

    def test_practice_uses_existing_workbench_and_giveup_updates_pool(self):
        item = self.add()
        problem = CFProblem(1704, "F", "Game", 2400)
        statement = ProblemStatement("CF1704F", "Game", "description", "input", "output", [])
        prepared = PreparedProblem(problem, statement, [], RatingRange(2400, 2400), "")
        with patch.object(self.web.service, "find_problem", return_value=problem), patch.object(self.web.service, "prepare_specific_problem", return_value=prepared):
            self.pool.post(self.alice, "practice", {"id": item["id"]})
        self.assertEqual(self.list()["items"][0]["status"], "picked")
        active = self.web.service.get_active_problem(self.web._actor(self.alice).scope_id)
        self.assertFalse(active.ranked)
        with patch.object(self.web.service, "giveup_wait_seconds", return_value=0):
            self.web._give_up(Handler(), self.alice)
        self.assertEqual(self.list()["items"][0]["status"], "skipped")
        self.assertEqual(self.list(self.bob)["items"][0]["status"], "new")

    def test_forced_training_giveup_updates_pool(self):
        item = self.add()
        self.record(item, "picked")
        actor = self.web._actor(self.alice)
        problem = CFProblem(1704, "F", "Game", 2400)
        statement = ProblemStatement("CF1704F", "Game", "description", "input", "output", [])
        self.web.service.store.set_active_problem(actor.scope_id, problem, statement, [], ranked=False)
        active = self.web.service.get_active_problem(actor.scope_id)
        self.web._set_single_challenge_control(self.alice, active, {})
        with self.pool.connect() as db:
            db.execute("update web_challenge_controls set giveup_at=? where user_id=?", ((datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat(), self.alice["user_id"]))
        self.assertIsNotNone(self.web._expire_single_challenge(self.alice))
        self.assertEqual(self.list()["items"][0]["status"], "skipped")

    def test_canonical_cf_alias_practice_ac_is_recognized(self):
        item = self.add("2263C2")
        canonical = CFProblem(2262, "A2", "Shared", 2400)
        statement = ProblemStatement("CF2262A2", "Shared", "description", "input", "output", [])
        prepared = PreparedProblem(canonical, statement, [], RatingRange(2400, 2400), "")
        with patch.object(self.web.service, "find_problem", return_value=canonical), patch.object(self.web.service, "prepare_specific_problem", return_value=prepared):
            self.pool.post(self.alice, "practice", {"id": item["id"]})
        self.web.service.store.record_submission(-1, self.alice["user_id"], "Alice", canonical, "idea", True, "OK", ranked=False)
        self.assertEqual(self.list()["items"][0]["status"], "ac")

    def test_validation_pagination_and_no_remote_dependency(self):
        with patch.object(self.web.service.cf, "fetch_problems", side_effect=AssertionError("must not fetch")):
            for i in range(25):
                self.add(f"P{1000+i}")
        self.assertEqual(len(self.list()["items"]), 24)
        self.assertEqual(len(self.list(page=2)["items"]), 1)
        self.assertEqual(self.list(page=999)["page"], 2)
        for fields in ({"rating": True}, {"rating": 4001}, {"tags": ["x"] * 11}, {"note": "x" * 501}):
            with self.subTest(fields=fields), self.assertRaises(ValueError):
                self.add("1704F", **fields)

    def test_http_routes_authentication_csrf_and_static_assets(self):
        unauth = Handler(path="/api/pool")
        self.web.handle_get(unauth, "/api/pool")
        self.assertEqual(unauth.status, 401)
        register = Handler({"username": "charlie", "displayName": "Charlie", "password": "password123"})
        self.web.handle_post(register, "/api/auth/register")
        cookie = register.response_headers["Set-Cookie"].split(";", 1)[0]
        csrf = register.json()["state"]["csrfToken"]
        invalid = Handler({"problemId": "P1001"}, cookie=cookie)
        self.web.handle_post(invalid, "/api/pool/problems")
        self.assertEqual(invalid.status, 403)
        valid = Handler({"problemId": "P1001"}, cookie=cookie, csrf=csrf)
        self.web.handle_post(valid, "/api/pool/problems")
        self.assertEqual(valid.status, 200)
        listing = Handler(path="/api/pool?platform=luogu&status=new", cookie=cookie)
        self.web.handle_get(listing, "/api/pool")
        self.assertEqual(listing.json()["total"], 1)
        self.assertEqual(listing.json()["csrfToken"], csrf)
        bad_query = Handler(path="/api/pool?page=nope", cookie=cookie)
        self.web.handle_get(bad_query, "/api/pool")
        self.assertEqual(bad_query.status, 400)
        for path in ("/pool", "/pool/", "/pool.js", "/pool.css"):
            response = Handler()
            self.assertTrue(self.web.handle_get(response, path))
            self.assertEqual(response.status, 200)


if __name__ == "__main__":
    unittest.main()
