import unittest
from unittest.mock import Mock

from qq_cf_bot.judge import _JUDGE_SYSTEM_PROMPT
from qq_cf_bot.models import ProblemStatement
from qq_cf_bot.prompt_skills import ORAL_JUDGE_SKILL, STATEMENT_RENDERING_SKILL
from qq_cf_bot.translator import OpenAIStatementTranslator, _STATEMENT_TRANSLATE_PROMPT


class PromptSkillTest(unittest.TestCase):
    def test_oral_judge_prompt_includes_calibration_skill(self):
        self.assertIn(ORAL_JUDGE_SKILL, _JUDGE_SYSTEM_PROMPT)
        self.assertIn("只喊算法名", _JUDGE_SYSTEM_PROMPT)
        self.assertIn("熟练选手补出", _JUDGE_SYSTEM_PROMPT)

    def test_statement_translate_prompt_includes_rendering_skill(self):
        self.assertIn(STATEMENT_RENDERING_SKILL, _STATEMENT_TRANSLATE_PROMPT)
        self.assertIn("ftlfloor", _STATEMENT_TRANSLATE_PROMPT)
        self.assertIn("10^9", _STATEMENT_TRANSLATE_PROMPT)
        self.assertIn("\\mid", _STATEMENT_TRANSLATE_PROMPT)
        self.assertIn("严格递增", _STATEMENT_TRANSLATE_PROMPT)
        self.assertIn("a_i lt a_{i+1}", STATEMENT_RENDERING_SKILL)
        self.assertIn("65\\,535", STATEMENT_RENDERING_SKILL)
        self.assertIn("a_i=<=ft[i/2]", STATEMENT_RENDERING_SKILL)

    def test_translated_statement_is_normalized_before_returning(self):
        translator = OpenAIStatementTranslator("http://llm", "key", "model", enabled=True)
        translator.client = Mock()
        translator.client.configured = True
        translator.client.complete_json.return_value = (
            '{"title":"T","description":"我们用 $$$d_v$$$ 表示深度。",'
            '"input_format":"限制 10 ^ 9，且 n 不超过 65\\\\,535。",'
            '"output_format":"将 a_p 替换为 ≤ftlfloordfraca_p2rfloor，保证 a_i=<=ft[i/2]。","hint":""}'
        )
        statement = ProblemStatement(
            pid="CF1A",
            title="Old",
            description="old",
            input_format="old",
            output_format="old",
            samples=[],
        )

        translated = translator.translate_statement(statement)

        self.assertEqual(translated.title, "T")
        self.assertIn("d_v", translated.description)
        self.assertIn("10^9", translated.input_format)
        self.assertIn("65,535", translated.input_format)
        self.assertNotIn("65\\,535", translated.input_format)
        self.assertIn("⌊a_p/2⌋", translated.output_format)
        self.assertIn("a_i=⌊i/2⌋", translated.output_format)
        self.assertNotIn("ftlfloor", translated.output_format)
        self.assertNotIn("<=ft", translated.output_format)

    def test_translator_retries_when_output_is_still_english(self):
        translator = OpenAIStatementTranslator("http://llm", "key", "model", enabled=True)
        translator.client = Mock()
        translator.client.configured = True
        translator.client.complete_json.side_effect = [
            (
                '{"title":"Commuting Permutation",'
                '"description":"Quack the Duck has a permutation a and an incomplete sequence b.",'
                '"input_format":"Each test contains multiple test cases.",'
                '"output_format":"For each test case, print YES if the answer exists.",'
                '"hint":"In the first test case, b=[1,2,3]."}'
            ),
            (
                '{"title":"可交换排列",'
                '"description":"小鸭 Quack 有一个排列 $$$a$$$ 和一个不完整的序列 $$$b$$$。",'
                '"input_format":"每个测试包含多个测试用例。",'
                '"output_format":"对于每个测试用例，如果答案存在则输出 YES。",'
                '"hint":"在第一个测试用例中，$$$b=[1,2,3]$$$。"}'
            ),
        ]
        statement = ProblemStatement(
            pid="CF1A",
            title="Commuting Permutation",
            description="Quack the Duck has a permutation a and an incomplete sequence b.",
            input_format="Each test contains multiple test cases.",
            output_format="For each test case, print YES if the answer exists.",
            hint="In the first test case, b=[1,2,3].",
            samples=[],
        )

        translated = translator.translate_statement(statement)

        self.assertEqual(translator.client.complete_json.call_count, 2)
        self.assertIn("小鸭", translated.description)
        self.assertIn("每个测试", translated.input_format)


if __name__ == "__main__":
    unittest.main()
