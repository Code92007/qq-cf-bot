import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from qq_cf_bot.models import CFProblem, CodeSubmission, RemoteJudgeResult
from qq_cf_bot.submitter import (
    CodeforcesForbiddenError,
    CodeforcesRemoteJudge,
    CodeforcesSubmissionError,
    _browser_headers,
    _choose_language_id,
    _diagnose_cf_block,
    _find_new_matching_submission,
    _extract_program_source,
    _extract_submission_ids,
    _friendly_cf_error,
    _parse_forms,
)


class SubmitterTest(unittest.TestCase):
    def test_choose_cpp_language_id_from_form(self):
        forms = _parse_forms(
            """
            <form action="/problemset/submit">
              <select name="programTypeId">
                <option value="54">GNU G++17 7.3.0</option>
                <option value="89">GNU G++20 13.2 (64 bit, winlibs)</option>
              </select>
              <textarea name="source"></textarea>
            </form>
            """
        )
        self.assertEqual(_choose_language_id(forms[0], "cpp"), "89")

    def test_choose_python_language_id_from_form(self):
        forms = _parse_forms(
            """
            <form>
              <select name="programTypeId">
                <option value="31">Python 3</option>
                <option value="70">PyPy 3-64</option>
              </select>
              <textarea name="source"></textarea>
            </form>
            """
        )
        self.assertEqual(_choose_language_id(forms[0], "py"), "70")

    def test_extract_submission_ids(self):
        html = """
        <a href="/contest/100/submission/123">123</a>
        <a href="/contest/100/submission/123">duplicate</a>
        <a href="/problemset/submission/100/124">124</a>
        """
        self.assertEqual(_extract_submission_ids(html, 100), [123, 124])

    def test_extract_program_source(self):
        html = '<pre id="program-source-text">int main() { return 0; }</pre>'
        self.assertEqual(_extract_program_source(html), "int main() { return 0; }")

    def test_browser_headers_look_like_form_post(self):
        headers = _browser_headers(referer="/problemset/submit/1/A", form=True)

        self.assertIn("Mozilla/5.0", headers["User-Agent"])
        self.assertEqual(headers["Origin"], "https://codeforces.com")
        self.assertEqual(headers["Referer"], "https://codeforces.com/problemset/submit/1/A")
        self.assertEqual(headers["Content-Type"], "application/x-www-form-urlencoded")

    def test_submit_falls_back_to_browser_after_forbidden(self):
        judge = CodeforcesRemoteJudge("tourist", "secret", "tourist")
        problem = CFProblem(1, "A", "Theatre Square", 1000)
        submission = CodeSubmission(language="cpp", source="int main(){return 0;}")
        calls = []
        resets = []
        browser_calls = []

        def fake_latest(_problem):
            return 0

        def fake_submit(_problem, _submission):
            calls.append(1)
            raise CodeforcesForbiddenError("403")

        def fake_poll(_problem, _before_id):
            return RemoteJudgeResult(True, "OK", "Accepted")

        judge._latest_matching_submission_id = fake_latest
        judge._submit = fake_submit
        judge._reset_session = lambda: resets.append(1)
        judge._submit_via_browser = lambda _problem, _submission: browser_calls.append(1)
        judge._poll_result = lambda _problem, _before_id, submitted_after=0: fake_poll(_problem, _before_id)

        result = judge.judge(problem, submission)

        self.assertTrue(result.accepted)
        self.assertEqual(len(calls), 1)
        self.assertEqual(len(resets), 1)
        self.assertEqual(len(browser_calls), 1)

    def test_submit_uses_browser_fallback_after_repeated_forbidden(self):
        judge = CodeforcesRemoteJudge("tourist", "secret", "tourist")
        problem = CFProblem(1, "A", "Theatre Square", 1000)
        submission = CodeSubmission(language="cpp", source="int main(){return 0;}")
        calls = []
        resets = []
        browser_calls = []

        judge._latest_matching_submission_id = lambda _problem: 0

        def fake_submit(_problem, _submission):
            calls.append(1)
            raise CodeforcesForbiddenError("403")

        judge._submit = fake_submit
        judge._reset_session = lambda: resets.append(1)
        judge._submit_via_browser = lambda _problem, _submission: browser_calls.append(1)
        judge._poll_result = lambda _problem, _before_id, submitted_after=0: RemoteJudgeResult(True, "OK", "Accepted")

        result = judge.judge(problem, submission)

        self.assertTrue(result.accepted)
        self.assertEqual(len(calls), 1)
        self.assertEqual(len(resets), 1)
        self.assertEqual(len(browser_calls), 1)

    def test_browser_fallback_failure_keeps_readable_reason(self):
        judge = CodeforcesRemoteJudge("tourist", "secret", "tourist")
        problem = CFProblem(1, "A", "Theatre Square", 1000)
        submission = CodeSubmission(language="cpp", source="int main(){return 0;}")

        judge._latest_matching_submission_id = lambda _problem: 0
        judge._submit = lambda _problem, _submission: (_ for _ in ()).throw(CodeforcesForbiddenError("403"))
        judge._reset_session = lambda: None
        judge._submit_via_browser = lambda _problem, _submission: (_ for _ in ()).throw(RuntimeError("Captcha needed"))

        with self.assertRaisesRegex(CodeforcesSubmissionError, "持久浏览器通道失败"):
            judge.judge(problem, submission)

    def test_persistent_browser_session_is_preferred_after_restart(self):
        with TemporaryDirectory() as tmp:
            session_dir = Path(tmp)
            judge = CodeforcesRemoteJudge("tourist", "secret", "tourist", session_dir=session_dir)
            judge._set_browser_session_ready(True)
            calls = []
            judge._submit_via_browser = lambda _problem, _submission: calls.append("browser")
            judge._submit = lambda _problem, _submission: calls.append("http")

            judge._submit_with_retry(
                CFProblem(1, "A", "Theatre Square", 1000),
                CodeSubmission(language="cpp", source="int main(){}"),
            )

            self.assertEqual(calls, ["browser"])
            self.assertIn("已缓存登录会话", judge.availability["message"])

    def test_verify_login_falls_back_to_browser_and_marks_ready(self):
        with TemporaryDirectory() as tmp:
            judge = CodeforcesRemoteJudge("tourist", "secret", "tourist", session_dir=Path(tmp))
            judge._ensure_logged_in = lambda: (_ for _ in ()).throw(CodeforcesForbiddenError("403"))
            judge._reset_session = lambda: None
            judge._verify_browser_login = lambda: judge._set_browser_session_ready(True)

            message = judge.verify_login()

            self.assertIn("已验证", message)
            self.assertTrue(judge._has_browser_session())

    def test_old_submission_is_not_matched_when_initial_probe_failed(self):
        problem = CFProblem(1, "A", "Theatre Square", 1000)
        submissions = [
            {
                "id": 100,
                "creationTimeSeconds": 1000,
                "problem": {"contestId": 1, "index": "A"},
            },
            {
                "id": 101,
                "creationTimeSeconds": 2000,
                "problem": {"contestId": 1, "index": "A"},
            },
        ]

        match = _find_new_matching_submission(submissions, problem, 0, submitted_after=1500)

        self.assertEqual(match["id"], 101)

    def test_cf_block_diagnostics(self):
        self.assertIn("人机验证", _diagnose_cf_block("<html>captcha required</html>"))
        self.assertIn("维护", _diagnose_cf_block("technical maintenance"))
        self.assertIn("风控", _diagnose_cf_block("<html>Cloudflare attention required</html>"))
        self.assertIn("人机验证", _friendly_cf_error("Captcha needed"))


if __name__ == "__main__":
    unittest.main()
