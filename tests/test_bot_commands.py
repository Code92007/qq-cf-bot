import unittest

from qq_cf_bot.bot import _needs_body_translation, _needs_statement_translation, _needs_title_translation, _parse_rating_range
from qq_cf_bot.models import ProblemStatement


class BotCommandTest(unittest.TestCase):
    def test_parse_rating_range(self):
        self.assertEqual(_parse_rating_range("1900 2600"), (1900, 2600))
        self.assertEqual(_parse_rating_range("rating 2100-2400"), (2100, 2400))
        self.assertEqual(_parse_rating_range("2600 1900"), (1900, 2600))
        self.assertEqual(_parse_rating_range("1200"), (1200, 1200))

    def test_reject_invalid_rating_range(self):
        self.assertIsNone(_parse_rating_range(""))
        self.assertIsNone(_parse_rating_range("abc"))
        self.assertIsNone(_parse_rating_range("700 2600"))
        self.assertIsNone(_parse_rating_range("1900 5000"))

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
