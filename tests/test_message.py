import unittest

from qq_cf_bot.message import (
    extract_plain_text,
    infer_code_language,
    is_at_only_mention,
    is_new_command,
    looks_like_code_text,
    parse_code_submission,
)


class MessageTest(unittest.TestCase):
    def test_plain_string_command(self):
        self.assertTrue(is_new_command("/new"))
        self.assertTrue(is_new_command(" /new  "))
        self.assertTrue(is_new_command("／new"))

    def test_cq_segments_are_ignored(self):
        self.assertEqual(extract_plain_text("[CQ:at,qq=123] /new"), " /new")
        self.assertTrue(is_new_command("[CQ:at,qq=123] /new"))

    def test_array_message(self):
        message = [
            {"type": "at", "data": {"qq": "123"}},
            {"type": "text", "data": {"text": " /new"}},
        ]
        self.assertTrue(is_new_command(message))

    def test_non_command(self):
        self.assertFalse(is_new_command("/newer"))
        self.assertFalse(is_new_command("hello"))

    def test_array_at_only_mention(self):
        message = [
            {"type": "at", "data": {"qq": "3849894908"}},
            {"type": "text", "data": {"text": " "}},
        ]
        self.assertTrue(is_at_only_mention(message, 3849894908))

    def test_array_at_with_text_is_not_at_only_mention(self):
        message = [
            {"type": "at", "data": {"qq": "3849894908"}},
            {"type": "text", "data": {"text": " /new"}},
        ]
        self.assertFalse(is_at_only_mention(message, 3849894908))

    def test_cq_at_only_mention(self):
        self.assertTrue(is_at_only_mention("[CQ:at,qq=3849894908]", 3849894908))
        self.assertFalse(is_at_only_mention("[CQ:at,qq=3849894908] /help", 3849894908))

    def test_parse_fenced_code_submission(self):
        parsed = parse_code_submission("```cpp\n#include <bits/stdc++.h>\nint main() {}\n```")
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed.language, "cpp")
        self.assertIn("#include", parsed.source)

    def test_parse_language_line_code_submission(self):
        parsed = parse_code_submission("python\nimport sys\nprint(1)")
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed.language, "python")
        self.assertEqual(parsed.source, "import sys\nprint(1)")

    def test_detect_direct_code(self):
        self.assertTrue(looks_like_code_text("#include <bits/stdc++.h>\nusing namespace std;\nint main(){return 0;}"))
        self.assertFalse(looks_like_code_text("今天讨论一下做法"))

    def test_infers_common_code_languages(self):
        self.assertEqual(infer_code_language("#include <bits/stdc++.h>\nusing namespace std;\nint main(){}"), "cpp")
        self.assertEqual(infer_code_language("#include <stdio.h>\nint main(){printf(\"1\");}"), "c")
        self.assertEqual(infer_code_language("public class Main { public static void main(String[] args){} }"), "java")
        self.assertEqual(infer_code_language("import sys\nprint(sys.stdin.readline())"), "python")

    def test_parse_bare_submitcode_uses_inferred_language(self):
        parsed = parse_code_submission("public class Main { public static void main(String[] args){} }")
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed.language, "java")


if __name__ == "__main__":
    unittest.main()
