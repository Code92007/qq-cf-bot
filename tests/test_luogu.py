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


if __name__ == "__main__":
    unittest.main()
