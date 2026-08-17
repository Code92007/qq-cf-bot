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

    def test_translated_statement_is_normalized_before_returning(self):
        translator = OpenAIStatementTranslator("http://llm", "key", "model", enabled=True)
        translator.client = Mock()
        translator.client.configured = True
        translator.client.complete_json.return_value = (
            '{"title":"T","description":"我们用 $$$d_v$$$ 表示深度。",'
            '"input_format":"限制 10 ^ 9。",'
            '"output_format":"将 a_p 替换为 ≤ftlfloordfraca_p2rfloor。","hint":""}'
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
        self.assertIn("⌊a_p/2⌋", translated.output_format)
        self.assertNotIn("ftlfloor", translated.output_format)


if __name__ == "__main__":
    unittest.main()
