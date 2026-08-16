import unittest

from qq_cf_bot.luogu import statement_from_luogu_problem


class LuoguTest(unittest.TestCase):
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
