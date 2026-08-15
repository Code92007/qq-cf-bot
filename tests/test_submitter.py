import unittest

from qq_cf_bot.submitter import _choose_language_id, _extract_program_source, _extract_submission_ids, _parse_forms


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


if __name__ == "__main__":
    unittest.main()
