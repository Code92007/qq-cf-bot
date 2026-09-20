import unittest
from unittest.mock import patch

from qq_cf_bot.luogu import LuoguClient, statement_from_luogu_problem
from qq_cf_bot.models import CFProblem


class LuoguTest(unittest.TestCase):
    def test_fetch_statement_accepts_current_data_envelope(self):
        client = LuoguClient()
        payload = {
            "status": 200,
            "data": {
                "problem": {
                    "pid": "CF2262A2",
                    "name": "Floor of MEX (Hard Version)",
                    "contenu": {
                        "name": "MEX 的下取整（困难版）",
                        "description": "中文题面",
                        "formatI": "中文输入",
                        "formatO": "中文输出",
                        "hint": "中文说明",
                    },
                    "samples": [["1\n1", "1"]],
                }
            },
        }
        with patch.object(client, "_fetch_json", return_value=payload):
            statement = client.fetch_statement(CFProblem(2262, "A2", "Floor of MEX", 1800))

        self.assertEqual(statement.pid, "CF2262A2")
        self.assertEqual(statement.title, "MEX 的下取整（困难版）")
        self.assertEqual(statement.description, "中文题面")
        self.assertEqual(statement.input_format, "中文输入")
        self.assertEqual(statement.output_format, "中文输出")
        self.assertEqual(statement.samples, [("1\n1", "1")])

    def test_extracts_problem_fields(self):
        statement = statement_from_luogu_problem(
            {
                "pid": "CF1A",
                "title": "剧院广场",
                "description": "题目描述",
                "inputFormat": "输入格式",
                "outputFormat": "输出格式",
                "samples": [["1 2 3", "4"]],
                "hint": "说明",
            },
            fallback_title="Theatre Square",
            source_url="https://example.test",
        )
        self.assertEqual(statement.pid, "CF1A")
        self.assertEqual(statement.title, "剧院广场")
        self.assertEqual(statement.samples, [("1 2 3", "4")])

    def test_normalizes_html_samples_without_losing_newlines(self):
        statement = statement_from_luogu_problem(
            {
                "pid": "CF2B",
                "title": "样例",
                "description": "题目描述",
                "samples": [
                    {
                        "input": "<div>3</div><div>1 0 0</div><div>0 1 0</div>",
                        "output": "2<br>3",
                    }
                ],
            },
            fallback_title="Samples",
            source_url="https://example.test",
        )

        self.assertEqual(statement.samples, [("3\n1 0 0\n0 1 0", "2\n3")])


if __name__ == "__main__":
    unittest.main()
