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
                "https://codeforces.com/contest/1/problem/A?locale=en",
                "https://m1.codeforces.com/problemset/problem/1/A?locale=en",
                "https://m1.codeforces.com/contest/1/problem/A?locale=en",
                "https://m2.codeforces.com/problemset/problem/1/A?locale=en",
                "https://m2.codeforces.com/contest/1/problem/A?locale=en",
            ),
        )

    def test_generates_problemset_variant_for_contest_page(self):
        variants = codeforces_url_variants(
            "https://m1.codeforces.com/contest/2051/problem/F",
            ("https://codeforces.com", "https://m1.codeforces.com"),
        )

        self.assertEqual(
            variants,
            (
                "https://codeforces.com/contest/2051/problem/F",
                "https://codeforces.com/problemset/problem/2051/F",
                "https://m1.codeforces.com/contest/2051/problem/F",
                "https://m1.codeforces.com/problemset/problem/2051/F",
            ),
        )

    def test_leaves_non_codeforces_url_alone(self):
        self.assertEqual(
            codeforces_url_variants("https://www.luogu.com.cn/problem/CF1A"),
            ("https://www.luogu.com.cn/problem/CF1A",),
        )


if __name__ == "__main__":
    unittest.main()
