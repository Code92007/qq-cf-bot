import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from qq_cf_bot.models import CFProblem, ProblemStatement
from qq_cf_bot.renderer import StatementRenderer, _normalize_statement_markup, _render_loose_math_tokens, _stash_math


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

    def test_math_is_rendered_as_readable_inline_html(self):
        rendered, fragments = _stash_math(_normalize_statement_markup(r"满足 $$$1 \le n \le 2 \cdot 10^5$$$ 且 $$$\texttt{0}$$$。"))
        html = rendered
        for token, fragment in fragments.items():
            html = html.replace(token, fragment)

        self.assertIn("≤", html)
        self.assertIn("·", html)
        self.assertIn("10<sup>5</sup>", html)
        self.assertIn("<code>0</code>", html)
        self.assertNotIn("$$$", html)

    def test_escaped_codeforces_math_delimiters_are_normalized(self):
        rendered, fragments = _stash_math(_normalize_statement_markup(r"排列长度为 \$\$\$n\$\$\$，区间为 $$$a[1 \ldots n]$$$。"))
        html = rendered
        for token, fragment in fragments.items():
            html = html.replace(token, fragment)

        self.assertIn("n", html)
        self.assertIn("…", html)
        self.assertNotIn("$$$", html)
        self.assertNotIn("ldots", html)

    def test_corrupted_floor_and_ceil_formula_text_is_repaired(self):
        text = _normalize_statement_markup("将 a_p 替换为 ≤ftlfloordfraca_p2rfloor，a_i 替换为 ≤ftlceildfraca_i2rceil。")

        self.assertIn("⌊a_p/2⌋", text)
        self.assertIn("⌈a_i/2⌉", text)
        self.assertNotIn("ftlfloor", text)
        self.assertNotIn("ftlceil", text)

    def test_split_subscript_spacing_is_compacted(self):
        text = _normalize_statement_markup("威廉写下了 n 个正整数 a_ 1, a_ 2, ..., a_ n。")

        self.assertIn("a_1", text)
        self.assertIn("a_2", text)
        self.assertIn("a_n", text)

    def test_subscript_and_power_math_are_rendered(self):
        rendered, fragments = _stash_math(_normalize_statement_markup(r"我们用 $$$d_v$$$ 表示顶点 $$$a_v$$$ 的深度，答案对 $$$10^9 + 7$$$ 取模。"))
        html = rendered
        for token, fragment in fragments.items():
            html = html.replace(token, fragment)

        self.assertIn("d<sub>v</sub>", html)
        self.assertIn("a<sub>v</sub>", html)
        self.assertIn("10<sup>9</sup>", html)
        self.assertNotIn("$$$", html)

    def test_nested_subscript_math_is_rendered(self):
        rendered, fragments = _stash_math(
            _normalize_statement_markup(r"要求 $$$a_{b_i}=b_{a_i}$$$，也就是 $$$b_{a_{i}}$$$。")
        )
        html = rendered
        for token, fragment in fragments.items():
            html = html.replace(token, fragment)

        self.assertIn("a<sub>b<sub>i</sub></sub>", html)
        self.assertIn("b<sub>a<sub>i</sub></sub>", html)
        self.assertNotIn("a<sub>b</sub>_i", html)

    def test_loose_nested_subscript_math_is_rendered(self):
        html = _render_loose_math_tokens("它必须满足 a_{p_i}=p_{a_i}，并且 b_{a_{i}} 合法。")

        self.assertIn("a<sub>p<sub>i</sub></sub>", html)
        self.assertIn("p<sub>a<sub>i</sub></sub>", html)
        self.assertIn("b<sub>a<sub>i</sub></sub>", html)

    def test_loose_math_tokens_are_repaired_after_markdown(self):
        html = _render_loose_math_tokens("变量 d_v，限制 10^9，残留 $$$，操作 ⌊a_p/2⌋。")

        self.assertIn("d<sub>v</sub>", html)
        self.assertIn("10<sup>9</sup>", html)
        self.assertIn("⌊a_p/2⌋", html)
        self.assertNotIn("$$$", html)

    def test_corrupted_mid_lt_and_sum_are_repaired(self):
        rendered, fragments = _stash_math(
            _normalize_statement_markup(
                "对于 $$$b^k mid x$$$，数组满足 $$$a_i lt a_{i+1}$$$。\n\n$$$Σ_i=2^n v(i,a_i)$$$"
            )
        )
        html = rendered
        for token, fragment in fragments.items():
            html = html.replace(token, fragment)

        self.assertIn("b<sup>k</sup> ∣ x", html)
        self.assertIn("a<sub>i</sub> &lt; a<sub>i+1</sub>", html)
        self.assertIn("∑<sub>i=2</sub><sup>n</sup>", html)
        self.assertIn("math-display", html)
        self.assertNotIn(" mid ", html)
        self.assertNotIn(" lt ", html)
        self.assertNotIn("Σ_i=2^n", html)


if __name__ == "__main__":
    unittest.main()
