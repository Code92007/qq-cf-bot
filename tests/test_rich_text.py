import json
from pathlib import Path
import unittest

from qq_cf_bot.regional import RegionalApplication
from qq_cf_bot.regional_editorials import render_editorial
from qq_cf_bot.rich_text import render_markdown
from qq_cf_bot.storage import _statement_from_json


class RichTextTest(unittest.TestCase):
    def test_chengdu_c_keeps_latex_and_formats_markdown(self):
        catalog = Path(__file__).resolve().parents[1] / "src/qq_cf_bot/catalog/regional_statements.json"
        statement = _statement_from_json(json.dumps(json.loads(catalog.read_text())["problems"]["icpc-2026-成都:C"]["statement"]))
        result = RegionalApplication.statement_json(statement)
        self.assertIn(r"\qquad", result["description"])
        self.assertIn(r"a_{i+1}-a_i\le 1", result["description"])
        self.assertIn("<strong>时间限制：</strong>2 秒", result["description"])
        self.assertIn(r"$1\le T\le 10^4$", result["input"])
        self.assertIn("$s_{p_j}=v_j$", result["description"])
        self.assertNotIn("**时间限制", result["description"])

    def test_statement_keeps_images_but_filters_active_html(self):
        result = render_markdown('![图示](../figure.png)\n\n<div><p>公式 $a_i < b_i$</p><script>bad()</script><img src="javascript:bad()" onerror="bad()"></div>', source_url="https://qoj.ac/problem/123", allow_images=True)
        self.assertIn('src="https://qoj.ac/figure.png"', result)
        self.assertIn("$a_i &lt; b_i$", result)
        for value in ("<script", "onerror", "javascript:", "bad()"):
            self.assertNotIn(value, result)

    def test_editorial_inequalities_and_math_survive_together(self):
        result = render_editorial('# 观察\n\nx<a：保留正文。$\\sum_{i=1}^n a_i$\n\n\\[a_{i+1} \\le b_i\\]\n\n```text\n$a_i$ < b\n```')
        self.assertIn("x&lt;a：保留正文", result)
        self.assertIn(r"$\sum_{i=1}^n a_i$", result)
        self.assertIn(r"\[a_{i+1} \le b_i\]", result)
        self.assertIn("<code>$a_i$ &lt; b", result)
