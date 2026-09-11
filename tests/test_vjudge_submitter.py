import json
import unittest

from qq_cf_bot.models import CFProblem, CodeSubmission
from qq_cf_bot.vjudge_submitter import (
    VJudgeRemoteJudge,
    _choose_vjudge_language_id,
    _extract_problem_submit_context,
    _normalize_vjudge_verdict,
    _parse_cookie_header,
    _result_from_vjudge,
)


class VJudgeSubmitterTest(unittest.TestCase):
    def test_extracts_submit_context_from_problem_page(self):
        payload = {
            "problemId": 1,
            "languages": {"54": "GNU G++17 7.3.0", "70": "PyPy 3-64"},
            "submitMethods": [True, False, False],
        }
        page = f"<html><body><textarea>{json.dumps(payload)}</textarea></body></html>"

        languages, methods = _extract_problem_submit_context(page)

        self.assertEqual(languages["54"], "GNU G++17 7.3.0")
        self.assertEqual(methods, [True, False, False])

    def test_chooses_vjudge_language_from_remote_options(self):
        languages = {
            "54": "GNU G++17 7.3.0",
            "89": "GNU G++20 13.2 (64 bit)",
            "70": "PyPy 3-64",
        }

        self.assertEqual(_choose_vjudge_language_id(languages, "cpp"), "89")
        self.assertEqual(_choose_vjudge_language_id(languages, "python"), "70")

    def test_parses_full_cookie_header(self):
        cookies = _parse_cookie_header("Cookie: JSESSIONID=abc; JSESSlONID=def")

        self.assertEqual(cookies, {"JSESSIONID": "abc", "JSESSlONID": "def"})

    def test_maps_vjudge_verdicts(self):
        self.assertEqual(_normalize_vjudge_verdict("AC"), "OK")
        self.assertEqual(_normalize_vjudge_verdict("Wrong Answer"), "WRONG_ANSWER")
        result = _result_from_vjudge(
            {"status": "Accepted", "statusCanonical": "AC", "runtime": 31},
            12345,
            "https://vjudge.net",
        )
        self.assertTrue(result.accepted)
        self.assertEqual(result.submission_id, 12345)
        self.assertEqual(result.time_ms, 31)
        self.assertEqual(result.url, "https://vjudge.net/solution/12345")

    def test_judge_uses_practice_default_account_and_polls_run(self):
        judge = VJudgeRemoteJudge(username="solver", password="secret", poll_interval_seconds=0)
        judge._ensure_logged_in = lambda: None
        judge._resolve_language_id = lambda _problem, _language: "89"
        calls = []

        def fake_post(path, fields, referer):
            calls.append((path, fields, referer))
            if path.startswith("/problem/submit/"):
                return '{"runId":12345}'
            return '{"runId":12345,"processing":false,"status":"Accepted","statusCanonical":"AC"}'

        judge._post = fake_post
        result = judge.judge(
            CFProblem(1, "A", "Theatre Square", 1000),
            CodeSubmission("cpp", "int main() { return 0; }"),
        )

        self.assertTrue(result.accepted)
        self.assertEqual(calls[0][0], "/problem/submit/CodeForces-1A")
        self.assertEqual(calls[0][1]["method"], "0")
        self.assertEqual(calls[0][1]["language"], "89")
        self.assertEqual(calls[0][1]["source"], "int main() { return 0; }")
        self.assertEqual(calls[1][0], "/solution/data/12345")


if __name__ == "__main__":
    unittest.main()
