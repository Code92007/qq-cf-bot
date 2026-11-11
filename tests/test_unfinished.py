import io
import json
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from email.message import Message
from unittest.mock import patch

from qq_cf_bot.config import Config
from qq_cf_bot.core import ChallengeError, ChallengeService
from qq_cf_bot.webapp import WebApplication


class Handler:
    def __init__(self, payload=None, path="", cookie="", csrf=""):
        body = json.dumps(payload or {}, ensure_ascii=False).encode()
        self.path = path
        self.headers = Message()
        self.headers["Content-Length"] = str(len(body))
        if cookie:
            self.headers["Cookie"] = cookie
        if csrf:
            self.headers["X-CSRF-Token"] = csrf
        self.rfile, self.wfile = io.BytesIO(body), io.BytesIO()
        self.status, self.response_headers = None, {}

    def send_response(self, status):
        self.status = status

    def send_header(self, key, value):
        self.response_headers[key] = value

    def end_headers(self):
        pass

    def json(self):
        return json.loads(self.wfile.getvalue())


class UnfinishedPoolTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        with patch.dict("os.environ", {"BOT_DATA_DIR": self.tmp.name, "CF_SUBMIT_ENABLED": "false",
                                      "JUDGE_ENABLED": "false", "WEB_COOKIE_SECURE": "false"}, clear=True):
            config = Config.from_env()
        self.web = WebApplication(config, ChallengeService(config))
        self.pool = self.web.unfinished
        self.alice, self.bob = [self.session(name) for name in ("alice", "bob")]

    def tearDown(self):
        self.tmp.cleanup()

    def session(self, name):
        user = self.web.service.store.create_web_user(name, name.title(), "unused-test-hash")
        return {"user_id": user["id"], "display_name": user["display_name"], "csrf_token": "csrf"}

    def save(self, item=None, session=None, **fields):
        payload = {"title": "想一半的题", "clientId": "test-draft-id"}
        if item:
            payload.update(item)
        payload.update(fields)
        return self.pool.post(session or self.alice, "save", payload)["item"]

    def status(self, item, status, session=None):
        return self.pool.post(session or self.alice, "status", {"id": item["id"], "revision": item["revision"], "status": status})["item"]

    def listing(self, session=None, **query):
        return self.pool.listing(session or self.alice, query)

    def test_drafts_preserve_code_and_resume_after_restart(self):
        code = "\n    // 半成品\n\tvector<int> dp(n);\r\n    return 0;\n\n"
        first = self.save(problemRef="1704F", idea="先从奇偶性分类", code=code, nextStep="验证 n 为奇数", language="cpp")
        self.assertEqual(first["code"], code)
        self.assertEqual(first["url"], "https://codeforces.com/problemset/problem/1704/F")
        edited = self.save(first, idea="已验证奇数，下一步证明", code=code + "// TODO\n")
        self.assertEqual(edited["revision"], first["revision"] + 1)
        self.assertEqual(edited["createdAt"], first["createdAt"])
        restarted = WebApplication(self.web.config, self.web.service)
        self.assertEqual(restarted.unfinished.entry(self.alice["user_id"], first["id"])["item"], edited)

    def test_each_user_has_private_entries_and_mutations(self):
        item = self.save(idea="私人思路", code="private_code")
        self.assertEqual(self.listing(self.bob)["items"], [])
        self.assertEqual(self.listing(self.bob, q="private_code")["total"], 0)
        for operation in [lambda: self.pool.entry(self.bob["user_id"], item["id"]),
                          lambda: self.save(item, self.bob, idea="覆盖"),
                          lambda: self.status(item, "done", self.bob)]:
            with self.assertRaises(ChallengeError) as cm:
                operation()
            self.assertEqual(cm.exception.status, 404)
        other = self.save(session=self.bob)
        self.assertNotEqual(item["id"], other["id"])
        self.assertEqual(self.pool.entry(self.alice["user_id"], item["id"])["item"]["idea"], "私人思路")

    def test_checking_off_is_reversible_and_keeps_drafts_without_awarding_ac(self):
        item = self.save(idea="idea", code="code", nextStep="next")
        before = self.web.service.get_user_stat(self.web._actor(self.alice))
        done = self.status(item, "done")
        self.assertTrue(done["completedAt"])
        self.assertEqual(self.listing()["counts"], {"open": 0, "done": 1, "all": 1})
        self.assertEqual(self.listing()["items"], [])
        self.assertEqual(self.status(done, "done")["completedAt"], done["completedAt"])
        edited = self.save(done, idea="收尾说明")
        self.assertEqual(edited["status"], "done")
        restored = self.status(edited, "open")
        self.assertEqual(restored["completedAt"], "")
        self.assertEqual((restored["idea"], restored["code"], restored["nextStep"]), ("收尾说明", "code", "next"))
        after = self.web.service.get_user_stat(self.web._actor(self.alice))
        self.assertEqual((before.rating, before.solved_count), (after.rating, after.solved_count))

    def test_search_includes_full_code_and_idea_and_paginates(self):
        item = self.save(title="博弈论", problemRef="1704F", idea="a" * 200 + "隐藏的结论", code="int NeedleUnique;", nextStep="验证边界")
        for q in ("博弈", "1704f", "隐藏的结论", "needleunique", "验证边界"):
            self.assertEqual(self.listing(q=q)["items"][0]["id"], item["id"])
        self.assertNotIn("code", self.listing()["items"][0])
        self.assertEqual(self.listing(q="不存在")["total"], 0)
        for i in range(31):
            self.save(clientId=f"pagination-{i}")
        first, last = self.listing(), self.listing(page=2)
        self.assertEqual((first["pages"], len(first["items"]), len(last["items"])), (2, 30, 2))
        self.assertFalse({p["id"] for p in first["items"]} & {p["id"] for p in last["items"]})
        self.status(item, "done")
        self.assertEqual(self.listing(status="done", q="needleunique")["total"], 1)

    def test_concurrent_edits_and_status_changes_cannot_overwrite_newer_content(self):
        item = self.save(idea="original")

        def edit(idea):
            try:
                return self.save(item, idea=idea)
            except ChallengeError as exc:
                return exc

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(edit, ("first", "second")))
        errors = [r for r in results if isinstance(r, ChallengeError)]
        self.assertEqual([e.code for e in errors], ["draft_conflict"])
        winner = next(r for r in results if isinstance(r, dict))
        with self.assertRaises(ChallengeError) as cm:
            self.status(item, "done")
        self.assertEqual(cm.exception.code, "draft_conflict")
        self.assertEqual(self.pool.entry(self.alice["user_id"], item["id"])["item"], winner)

    def test_retrying_creation_is_idempotent_and_does_not_overwrite_a_later_edit(self):
        first = self.save(idea="original")
        latest = self.save(first, idea="newer")
        retried = self.save(idea="old retry")
        self.assertEqual(retried, latest)
        self.assertEqual(self.listing()["total"], 1)

    def test_code_only_and_arbitrary_problem_references(self):
        code_only = self.save(title="", code="    partial();\n")
        self.assertEqual(code_only["title"], "未命名的题目")
        item = self.save(code_only, problemRef="https://example.org/custom/problem/42")
        self.assertEqual(item["url"], item["problemRef"])
        unsafe = self.save(item, problemRef="javascript:alert(1)")
        self.assertEqual(unsafe["url"], "")

    def test_invalid_input_does_not_create_or_corrupt_a_draft(self):
        for payload in ({"title": ""}, {"title": "x" * 121}, {"idea": []}, {"code": "x" * 128001},
                        {"language": []}, {"language": "invalid"}, {"nextStep": "\x00"}, {"clientId": "bad"}):
            with self.subTest(payload=list(payload)):
                with self.assertRaises(ChallengeError) as cm:
                    self.save(**payload)
                self.assertEqual(cm.exception.status, 400)
        item = self.save()
        for fields in ({"revision": 0}, {"id": True}, {"id": -1}):
            with self.assertRaises(ChallengeError):
                self.save(item, **fields)
        self.assertEqual(self.pool.entry(self.alice["user_id"], item["id"])["item"], item)

    def test_http_auth_csrf_validation_and_large_unicode_code(self):
        unauthenticated = Handler()
        self.web.handle_get(unauthenticated, "/api/unfinished")
        self.assertEqual(unauthenticated.status, 401)
        register = Handler({"username": "carol", "displayName": "Carol", "password": "password123"})
        self.web.handle_post(register, "/api/auth/register")
        cookie = register.response_headers["Set-Cookie"].split(";", 1)[0]
        csrf = register.json()["state"]["csrfToken"]
        blocked = Handler({"title": "blocked"}, cookie=cookie)
        self.web.handle_post(blocked, "/api/unfinished/save")
        self.assertEqual(blocked.status, 403)
        payload = {"clientId": "unicode-code", "code": "码" * 128000, "idea": "想" * 20000, "language": "other"}
        saved = Handler(payload, cookie=cookie, csrf=csrf)
        self.web.handle_post(saved, "/api/unfinished/save")
        self.assertEqual(saved.status, 200)
        self.assertEqual(saved.json()["item"]["code"], payload["code"])
        for path in ("/api/unfinished?status=bad", "/api/unfinished?page=-1", "/api/unfinished/entry?id=bad"):
            handler = Handler(path=path, cookie=cookie)
            self.web.handle_get(handler, path.split("?", 1)[0])
            self.assertEqual(handler.status, 400)


if __name__ == "__main__":
    unittest.main()
