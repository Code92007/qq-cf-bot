import unittest

from qq_cf_bot.cf_mirrors import codeforces_url_variants, normalize_codeforces_base_urls


class CodeforcesMirrorTest(unittest.TestCase):
    def test_normalizes_configured_base_urls(self):
        self.assertEqual(
            normalize_codeforces_base_urls("codeforces.com, https://m1.codeforces.com/;m1.codeforces.com"),
            ("https://codeforces.com", "https://m1.codeforces.com"),
        )

    def test_generates_problem_page_variants(self):
        variants = codeforces_url_variants(
            "https://codeforces.com/problemset/problem/1/A?locale=en",
            ("https://codeforces.com", "https://m1.codeforces.com", "https://m2.codeforces.com"),
        )

        self.assertEqual(
            variants,
            (
                "https://codeforces.com/problemset/problem/1/A?locale=en",
                "https://m1.codeforces.com/problemset/problem/1/A?locale=en",
                "https://m2.codeforces.com/problemset/problem/1/A?locale=en",
            ),
        )

    def test_leaves_non_codeforces_url_alone(self):
        self.assertEqual(
            codeforces_url_variants("https://www.luogu.com.cn/problem/CF1A"),
            ("https://www.luogu.com.cn/problem/CF1A",),
        )


if __name__ == "__main__":
    unittest.main()
