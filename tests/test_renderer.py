import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from qq_cf_bot.models import CFProblem, ProblemStatement
from qq_cf_bot.renderer import StatementRenderer


class StatementRendererTest(unittest.TestCase):
    def test_can_hide_problem_metadata(self):
        problem = CFProblem(28, "D", "Don't fear, DravDe is kind", 2400, ("dp",))
        statement = ProblemStatement(
            pid="CF28D",
            title="不要害怕，DravDe 很善良",
            description="题目描述",
            input_format="输入格式",
            output_format="输出格式",
            samples=[],
            source_url=problem.luogu_url,
        )
        with tempfile.TemporaryDirectory() as tmp:
            renderer = StatementRenderer(Path(tmp))
            with patch("qq_cf_bot.renderer._markdown_to_html", side_effect=lambda text, source_url="": text):
                html = "".join(renderer._build_cards(problem, statement, reveal_metadata=False))

        self.assertIn("题目描述", html)
        self.assertNotIn("Don't fear", html)
        self.assertNotIn("2400", html)
        self.assertNotIn("codeforces.com", html)
        self.assertNotIn("luogu.com.cn", html)


if __name__ == "__main__":
    unittest.main()
