import unittest

from qq_cf_bot.models import CFProblem, CodeSubmission, RemoteJudgeResult
from qq_cf_bot.submitter import (
    CodeforcesForbiddenError,
    CodeforcesRemoteJudge,
    _browser_headers,
    _choose_language_id,
    _extract_program_source,
    _extract_submission_ids,
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

    def test_submit_retries_once_after_forbidden(self):
        judge = CodeforcesRemoteJudge("tourist", "secret", "tourist")
        problem = CFProblem(1, "A", "Theatre Square", 1000)
        submission = CodeSubmission(language="cpp", source="int main(){return 0;}")
        calls = []
        resets = []

        def fake_latest(_problem):
            return 0

        def fake_submit(_problem, _submission):
            calls.append(1)
            if len(calls) == 1:
                raise CodeforcesForbiddenError("403")

        def fake_poll(_problem, _before_id):
            return RemoteJudgeResult(True, "OK", "Accepted")

        judge._latest_matching_submission_id = fake_latest
        judge._submit = fake_submit
        judge._reset_session = lambda: resets.append(1)
        judge._poll_result = fake_poll

        result = judge.judge(problem, submission)

        self.assertTrue(result.accepted)
        self.assertEqual(len(calls), 2)
        self.assertEqual(len(resets), 1)


if __name__ == "__main__":
    unittest.main()
