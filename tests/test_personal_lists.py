import unittest
from unittest.mock import patch

from qq_cf_bot.models import JudgeResult, ProblemStatement
from qq_cf_bot.personal_lists import _display_statement, parse_entries
from test_webapp import WebApplicationTest, _Handler


class PersonalListsTest(WebApplicationTest):
    def _register(self, name):
        handler = _Handler({"username": name, "displayName": name, "password": "password123"})
        self.app.handle_post(handler, "/api/auth/register")
        self.assertEqual(handler.status, 201)
        return handler.header("Set-Cookie").split(";", 1)[0], handler.json()["state"]["csrfToken"]

    def _post(self, path, body, auth):
        handler = _Handler(body, cookie=auth[0], csrf=auth[1])
        self.app.handle_post(handler, path)
        return handler

    def _get(self, path, auth=None):
        handler = _Handler(cookie=auth[0] if auth else "")
        handler.path = path
        self.app.handle_get(handler, path.split("?", 1)[0])
        return handler

    def test_private_lists_and_csrf(self):
        alice = self._register("alice")
        bob = self._register("bobby")
        created = self._post("/api/lists/create", {"name": "我的题单", "text": "# 提高\nP1001 CF1704F"}, alice)
        self.assertEqual(created.status, 200)
        list_id = created.json()["id"]
        alice_entries = self._get(f"/api/lists/entries?id={list_id}", alice)
        self.assertEqual([item["problemId"] for item in alice_entries.json()["entries"]], ["P1001", "CF1704F"])
        self.assertEqual(alice_entries.json()["entries"][1]["url"], "https://www.luogu.com.cn/problem/CF1704F")
        entry_id = alice_entries.json()["entries"][0]["id"]
        self.assertEqual(self._get("/api/lists", bob).json()["lists"], [])
        self.assertEqual(self._get(f"/api/lists/entries?id={list_id}", bob).status, 404)
        self.assertEqual(self._post("/api/lists/open", {"entryId": entry_id}, bob).status, 404)
        self.assertEqual(self._post("/api/lists/delete", {"listId": list_id}, bob).status, 404)
        self.assertEqual(self._post("/api/lists/draft", {"entryId": entry_id, "text": "偷改", "version": 0}, bob).status, 404)
        self.assertEqual(self._post("/api/lists/status", {"entryId": entry_id, "status": "done"}, bob).status, 404)
        self.assertEqual(self._get("/api/lists").status, 401)
        self.assertEqual(self.app.handle_post(_Handler({"listId": list_id}, cookie=alice[0]), "/api/lists/delete"), True)
        self.assertEqual(self._get(f"/api/lists/entries?id={list_id}", alice).status, 200)

    def test_draft_attempt_and_restart(self):
        alice = self._register("alice")
        list_id = self._post("/api/lists/create", {"name": "训练"}, alice).json()["id"]
        self.assertEqual(self._post("/api/lists/add", {"listId": list_id, "group": "提高", "text": "P1001 P1001"}, alice).json(),
                         {"added": 1, "duplicates": 0})
        entry_id = self._get(f"/api/lists/entries?id={list_id}", alice).json()["entries"][0]["id"]
        self.assertEqual(self._post("/api/lists/draft", {"entryId": entry_id, "text": "观察", "version": 0}, alice).status, 200)
        self.assertEqual(self._post("/api/lists/draft", {"entryId": entry_id, "text": "旧版本", "version": 0}, alice).status, 409)
        self.assertEqual(self._post("/api/lists/oral", {"entryId": entry_id, "body": "方法", "requestId": "request-123"}, alice).status, 503)
        self._post("/api/lists/statement", {"entryId": entry_id, "text": "求两个数的和。"}, alice)
        with patch.object(type(self.app.service.judge), "configured", new_callable=lambda: property(lambda _: True)):
            with patch.object(self.app.service.judge, "judge", return_value=JudgeResult(True, "思路正确。")) as judge:
                result = self._post("/api/lists/oral", {"entryId": entry_id, "body": "读入并相加。", "requestId": "request-123"}, alice)
                self.assertEqual(result.status, 200)
                self.assertTrue(result.json()["accepted"])
                self.assertEqual(self._post("/api/lists/oral", {"entryId": entry_id, "body": "读入并相加。", "requestId": "request-123"}, alice).json(), result.json())
                self.assertEqual(judge.call_count, 1)
        self.assertEqual(self._post("/api/lists/oral", {"entryId": entry_id, "body": "另一份", "requestId": "request-123"}, alice).status, 409)
        self.assertEqual(self._post("/api/lists/open", {"entryId": entry_id}, alice).json()["entry"]["status"], "done")
        from qq_cf_bot.personal_lists import PersonalLists
        restarted = PersonalLists(self.app)
        self.assertEqual(restarted.detail(self.app.service.store.get_web_user_by_username("alice")["id"], entry_id)["attempts"][0]["reason"], "思路正确。")

    def test_bulk_import_is_atomic_and_grouped(self):
        alice = self._register("alice")
        created = self._post("/api/lists/create", {"name": "组", "text": "# 一\nP1001 P1002\n# 二\nAT_abc160_f CF77B SP1043"}, alice)
        self.assertEqual(created.json()["added"], 5)
        list_id = created.json()["id"]
        entries = self._get(f"/api/lists/entries?id={list_id}", alice).json()["entries"]
        self.assertEqual([item["group"] for item in entries], ["一", "一", "二", "二", "二"])
        invalid = self._post("/api/lists/add", {"listId": list_id, "text": "P1003 invalid!"}, alice)
        self.assertEqual(invalid.status, 400)
        self.assertEqual(len(self._get(f"/api/lists/entries?id={list_id}", alice).json()["entries"]), 5)
        self.assertEqual(len(parse_entries("# 提高\nP1001 CF77B")), 2)

    def test_luogu_problem_fetch_uses_real_id(self):
        alice = self._register("alice")
        list_id = self._post("/api/lists/create", {"name": "洛谷", "text": "P1001"}, alice).json()["id"]
        entry_id = self._get(f"/api/lists/entries?id={list_id}", alice).json()["entries"][0]["id"]
        statement = ProblemStatement("P1001", "A+B", "求和", "输入", "输出", [])
        with patch.object(self.app.service.luogu, "fetch_problem_id", return_value=statement) as fetch:
            opened = self._post("/api/lists/open", {"entryId": entry_id, "prepareStatement": True}, alice)
        self.assertEqual(opened.json()["statement"]["title"], "A+B")
        fetch.assert_called_once_with("P1001")

    def test_statement_markup_is_rendered_and_sanitized(self):
        statement = _display_statement({"description": "**重点** <script>alert(1)</script>\n\n| A | B |\n|---|---|\n| 1 | 2 |",
                                        "sourceUrl": "https://www.luogu.com.cn/problem/P1001"})
        rendered = statement["html"]["description"]
        self.assertIn("<strong>重点</strong>", rendered)
        self.assertIn("<table>", rendered)
        self.assertNotIn("<script", rendered)
        self.assertNotIn("alert(1)", rendered)

    def test_unrenderable_statement_keeps_raw_text(self):
        with patch("qq_cf_bot.personal_lists._markdown_to_html", side_effect=ValueError("invalid markup")):
            statement = _display_statement({"description": "原题内容", "sourceUrl": ""})
        self.assertEqual(statement["description"], "原题内容")
        self.assertEqual(statement["html"], {})


if __name__ == "__main__":
    unittest.main()
