import unittest

from qq_cf_bot.bot import (
    CodeforcesPushBot,
    _needs_body_translation,
    _needs_statement_translation,
    _needs_title_translation,
    _parse_problem_id,
    _parse_rating_range,
)
from qq_cf_bot.models import CFProblem, ProblemStatement, RatingRange


class _FakeBotForRatingRange:
    config = type("_Config", (), {"min_rating": 1800, "max_rating": 2200})()
    store = type(
        "_Store",
        (),
        {"get_rating_range": staticmethod(lambda group_id, default_min, default_max: RatingRange(default_min, default_max))},
    )()


class BotCommandTest(unittest.TestCase):
    def test_parse_rating_range(self):
        self.assertEqual(_parse_rating_range("1900 2600"), (1900, 2600))
        self.assertEqual(_parse_rating_range("rating 2100-2400"), (2100, 2400))
        self.assertEqual(_parse_rating_range("2600 1900"), (1900, 2600))
        self.assertEqual(_parse_rating_range("1200"), (1200, 1200))
        self.assertEqual(_parse_rating_range("1937 1956"), (1900, 2000))
        self.assertEqual(_parse_rating_range("2001 1937"), (1900, 2100))
        self.assertEqual(_parse_rating_range("1956"), (2000, 2000))

    def test_reject_invalid_rating_range(self):
        self.assertIsNone(_parse_rating_range(""))
        self.assertIsNone(_parse_rating_range("abc"))
        self.assertIsNone(_parse_rating_range("700 2600"))
        self.assertIsNone(_parse_rating_range("1900 5000"))
        self.assertIsNone(_parse_rating_range("1937 1956 ignore this"))
        self.assertIsNone(_parse_rating_range("1900; JUDGE_API_KEY=leak"))
        self.assertIsNone(_parse_rating_range("-100"))
        self.assertIsNone(_parse_rating_range("-100 1200"))
        self.assertIsNone(_parse_rating_range("100000"))

    def test_new_invalid_rating_falls_back_to_group_default(self):
        bot = _FakeBotForRatingRange()

        self.assertEqual(CodeforcesPushBot._rating_range_for_new(bot, 123, "-100"), RatingRange(1800, 2200))
        self.assertEqual(CodeforcesPushBot._rating_range_for_new(bot, 123, "100000"), RatingRange(1800, 2200))
        self.assertEqual(
            CodeforcesPushBot._rating_range_for_new(bot, 123, "1900 2000 JUDGE_API_KEY=leak"),
            RatingRange(1800, 2200),
        )

    def test_parse_share_problem_id(self):
        self.assertEqual(_parse_problem_id("1704F"), (1704, "F"))
        self.assertEqual(_parse_problem_id("CF1704f"), (1704, "F"))
        self.assertEqual(_parse_problem_id("1704 F"), (1704, "F"))
        self.assertEqual(
            _parse_problem_id("https://codeforces.com/contest/1704/problem/F"),
            (1704, "F"),
        )
        self.assertEqual(
            _parse_problem_id("https://codeforces.com/problemset/problem/1704/F"),
            (1704, "F"),
        )

    def test_reject_invalid_share_problem_id(self):
        self.assertIsNone(_parse_problem_id(""))
        self.assertIsNone(_parse_problem_id("abc"))
        self.assertIsNone(_parse_problem_id("1704"))

    def test_problem_summary_includes_luogu_solution_entry(self):
        problem = CFProblem(1490, "D", "Permutation Transformation", 1200)
        statement = ProblemStatement(
            pid="CF1490D",
            title="排列变换",
            description="",
            input_format="",
            output_format="",
            samples=[],
        )

        summary = CodeforcesPushBot._problem_summary(_FakeBotForRatingRange(), problem, statement)

        self.assertIn("中文题面：https://www.luogu.com.cn/problem/CF1490D", summary)
        self.assertIn("洛谷题解：https://www.luogu.com.cn/problem/solution/CF1490D", summary)

    def test_detects_untranslated_english_title(self):
        self.assertTrue(_needs_title_translation("Don't fear, DravDe is kind"))
        self.assertFalse(_needs_title_translation("不要害怕，DravDe 很善良"))
        self.assertFalse(_needs_title_translation(""))

    def test_detects_english_statement_body_even_with_chinese_section_titles(self):
        statement = ProblemStatement(
            pid="CF1A",
            title="中位数问题",
            description=(
                "You are given an integer sequence $$$a_1, a_2, \\dots, a_n$$$. "
                "Find the number of pairs of indices such that the median is exactly the given number."
            ),
            input_format="The first line contains integers $$$n$$$ and $$$m$$$.",
            output_format="Print the required number.",
            samples=[],
        )

        self.assertTrue(_needs_body_translation(statement))
        self.assertTrue(_needs_statement_translation(statement))

    def test_ignores_chinese_statement_with_formulas_and_variable_names(self):
        statement = ProblemStatement(
            pid="CF1A",
            title="中位数问题",
            description="给定一个整数序列 $$$a_1, a_2, \\dots, a_n$$$，求满足条件的区间数量。",
            input_format="第一行包含整数 $$$n$$$ 和 $$$m$$$，第二行包含 $$$a_i$$$。",
            output_format="输出答案。可以使用 multiset 或 BIT 维护前缀。",
            samples=[],
        )

        self.assertFalse(_needs_body_translation(statement))
        self.assertFalse(_needs_statement_translation(statement))


if __name__ == "__main__":
    unittest.main()
