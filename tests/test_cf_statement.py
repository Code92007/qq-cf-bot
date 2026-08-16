import unittest

from qq_cf_bot.cf_statement import statement_from_codeforces_html
from qq_cf_bot.models import CFProblem


class CodeforcesStatementTest(unittest.TestCase):
    def test_extracts_statement_fields(self):
        problem = CFProblem(1, "A", "Theatre Square", 1000, ("math",))
        html = """
        <html><body>
        <div class="problem-statement">
          <div class="header"><div class="title">A. Theatre Square</div></div>
          <div><p>Theatre Square has size <span class="tex-span">n×m</span>.</p></div>
          <div class="input-specification">
            <div class="section-title">Input</div>
            <p>Three positive integers.</p>
          </div>
          <div class="output-specification">
            <div class="section-title">Output</div>
            <p>Print the answer.</p>
          </div>
          <div class="sample-tests">
            <div class="sample-test">
              <div class="input"><div class="title">Input</div><pre>6 6 4</pre></div>
              <div class="output"><div class="title">Output</div><pre>4</pre></div>
            </div>
          </div>
          <div class="note"><div class="section-title">Note</div><p>No note.</p></div>
        </div>
        </body></html>
        """

        statement = statement_from_codeforces_html(problem, html)

        self.assertEqual(statement.pid, "1A")
        self.assertEqual(statement.title, "A. Theatre Square")
        self.assertIn("Theatre Square", statement.description)
        self.assertIn("Three positive integers", statement.input_format)
        self.assertEqual(statement.samples, [("6 6 4", "4")])
        self.assertIn("No note", statement.hint)

    def test_preserves_codeforces_multiline_sample_divs(self):
        problem = CFProblem(2, "B", "Samples", 1200)
        html = """
        <div class="problem-statement">
          <div class="header"><div class="title">B. Samples</div></div>
          <div><p>desc</p></div>
          <div class="sample-tests">
            <div class="sample-test">
              <div class="input"><div class="title">Input</div><pre>
                <div class="test-example-line">3</div>
                <div class="test-example-line">1 0 0</div>
                <div class="test-example-line">0 1 0</div>
              </pre></div>
              <div class="output"><div class="title">Output</div><pre>
                <div class="test-example-line">2</div>
                <div class="test-example-line">3</div>
              </pre></div>
            </div>
          </div>
        </div>
        """

        statement = statement_from_codeforces_html(problem, html)

        self.assertEqual(statement.samples, [("3\n1 0 0\n0 1 0", "2\n3")])


if __name__ == "__main__":
    unittest.main()
