import tempfile
import unittest
from pathlib import Path

from qq_cf_bot.models import CFProblem, PreparedProblem, ProblemStatement, RatingRange, RemoteJudgeResult, SolutionReference
from qq_cf_bot.storage import SentProblemStore


class StorageTest(unittest.TestCase):
    def test_active_problem_roundtrip_and_sent_ids(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = SentProblemStore(Path(tmp) / "bot.sqlite3")
            problem = CFProblem(1042, "D", "Petya and Array", 1800, ("data structures",))
            statement = ProblemStatement(
                pid="CF1042D",
                title="Petya and Array",
                description="desc",
                input_format="in",
                output_format="out",
                samples=[("1", "2")],
            )
            store.mark_sent(123, problem)
            store.set_active_problem(123, problem, statement, [Path("/tmp/a.png"), Path("/tmp/b.png")])

            self.assertEqual(store.sent_ids(123), {"1042D"})
            active = store.get_active_problem(123)
            self.assertIsNotNone(active)
            self.assertEqual(active.problem.cf_id, "1042D")
            self.assertEqual(active.statement.samples, [("1", "2")])
            self.assertEqual([str(path) for path in active.images], ["/tmp/a.png", "/tmp/b.png"])

            store.clear_active_problem(123)
            self.assertIsNone(store.get_active_problem(123))

    def test_statement_cache_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = SentProblemStore(Path(tmp) / "bot.sqlite3")
            problem = CFProblem(1, "A", "Theatre Square", 1000)
            statement = ProblemStatement(
                pid="1A",
                title="剧院广场",
                description="题目描述",
                input_format="输入",
                output_format="输出",
                samples=[("1", "2")],
                source_url="https://codeforces.com/problemset/problem/1/A",
            )

            self.assertIsNone(store.get_cached_statement("1A"))
            store.cache_statement(problem, statement, source="codeforces_llm_translate", translated=True)

            cached = store.get_cached_statement("1A")
            self.assertIsNotNone(cached)
            self.assertEqual(cached.title, "剧院广场")
            self.assertEqual(cached.samples, [("1", "2")])

    def test_statement_cache_can_require_translated(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = SentProblemStore(Path(tmp) / "bot.sqlite3")
            problem = CFProblem(1, "A", "Theatre Square", 1000)
            english = ProblemStatement(
                pid="1A",
                title="Theatre Square",
                description="English",
                input_format="Input",
                output_format="Output",
                samples=[],
            )
            chinese = ProblemStatement(
                pid="1A",
                title="剧院广场",
                description="中文",
                input_format="输入",
                output_format="输出",
                samples=[],
            )

            store.cache_statement(problem, english, source="codeforces", translated=False)
            self.assertIsNotNone(store.get_cached_statement("1A"))
            self.assertIsNone(store.get_cached_statement("1A", require_translated=True))

            store.cache_statement(problem, chinese, source="codeforces_llm_translate", translated=True)
            self.assertEqual(store.get_cached_statement("1A", require_translated=True).title, "剧院广场")

    def test_prefetched_problem_roundtrip_and_clear(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = SentProblemStore(Path(tmp) / "bot.sqlite3")
            prepared = PreparedProblem(
                problem=CFProblem(1, "A", "Theatre Square", 1000),
                statement=ProblemStatement(
                    pid="1A",
                    title="剧院广场",
                    description="题目描述",
                    input_format="输入",
                    output_format="输出",
                    samples=[],
                ),
                images=[Path("/tmp/a.png")],
                rating_range=RatingRange(1000, 1000),
                created_at="now",
            )

            store.set_prefetched_problem(123, prepared)
            cached = store.get_prefetched_problem(123, RatingRange(1000, 1000))
            self.assertIsNotNone(cached)
            self.assertEqual(cached.problem.cf_id, "1A")
            self.assertEqual(cached.rating_range.min_rating, 1000)
            self.assertIsNone(store.get_prefetched_problem(123, RatingRange(1200, 1200)))

            store.clear_prefetched_problem(123, RatingRange(1000, 1000))
            self.assertIsNone(store.get_prefetched_problem(123, RatingRange(1000, 1000)))

    def test_user_stats(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = SentProblemStore(Path(tmp) / "bot.sqlite3")
            stat = store.get_user_stat(1, 2, "alice", 1500)
            self.assertEqual(stat.rating, 1500)

            updated = store.mark_solved(1, 2, "Alice", 1532.5, 1500)
            self.assertEqual(updated.solved_count, 1)
            stats = store.list_group_stats(1)
            self.assertEqual(stats[0].display_name, "Alice")
            self.assertEqual(stats[0].solved_count, 1)

    def test_group_stats_rank_by_solved_rating_vector(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = SentProblemStore(Path(tmp) / "bot.sqlite3")
            hard = CFProblem(1, "A", "Hard", 2600)
            lower_a = CFProblem(2, "A", "Lower A", 2500)
            lower_b = CFProblem(3, "A", "Lower B", 2500)
            for problem in (hard, lower_a, lower_b):
                store.mark_sent(1, problem)

            store.record_submission(1, 10, "hard", hard, "ok", True, "通过")
            store.mark_solved(1, 10, "hard", 1600, 1500)
            store.record_submission(1, 20, "farmer", lower_a, "ok", True, "通过")
            store.mark_solved(1, 20, "farmer", 1800, 1500)
            store.record_submission(1, 20, "farmer", lower_b, "ok", True, "通过")
            store.mark_solved(1, 20, "farmer", 1900, 1500)

            stats = store.list_group_stats(1)

            self.assertEqual([stat.display_name for stat in stats], ["hard", "farmer"])
            self.assertEqual(stats[0].solved_ratings, (2600,))
            self.assertEqual(stats[1].solved_ratings, (2500, 2500))

    def test_group_rating_range_and_meta(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = SentProblemStore(Path(tmp) / "bot.sqlite3")
            self.assertEqual(store.get_rating_range(1, 1900, 2600).min_rating, 1900)
            self.assertEqual(store.get_rating_range(1, 1900, 2600).max_rating, 2600)

            store.set_rating_range(1, 2100, 2400)
            rating_range = store.get_rating_range(1, 1900, 2600)
            self.assertEqual((rating_range.min_rating, rating_range.max_rating), (2100, 2400))

            store.set_meta_float("cf_last_submit_at", 123.5)
            self.assertEqual(store.get_meta_float("cf_last_submit_at"), 123.5)

    def test_submission_history_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = SentProblemStore(Path(tmp) / "bot.sqlite3")
            problem = CFProblem(1, "A", "Theatre Square", 1000)
            store.record_submission(1, 2, "alice", problem, "想法一", False, "不够")
            store.record_submission(1, 3, "bob", problem, "想法二", True, "通过")

            history = store.list_submission_history(1, "1A")

            self.assertEqual([item["display_name"] for item in history], ["alice", "bob"])
            self.assertFalse(history[0]["accepted"])
            self.assertTrue(history[1]["accepted"])

    def test_records_remote_code_submission_without_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = SentProblemStore(Path(tmp) / "bot.sqlite3")
            problem = CFProblem(1, "A", "Theatre Square", 1000)
            result = RemoteJudgeResult(
                accepted=True,
                verdict="OK",
                message="Accepted",
                submission_id=42,
                passed_tests=10,
                time_ms=46,
                memory_bytes=102400,
                url="https://codeforces.com/contest/1/submission/42",
            )
            store.record_code_submission(1, 2, "alice", problem, "cpp", "hash", 120, result)

    def test_solution_references_roundtrip_and_dedupe(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = SentProblemStore(Path(tmp) / "bot.sqlite3")
            reference = SolutionReference(
                cf_id="1A",
                source="luogu",
                title="题解",
                author="alice",
                url="https://www.luogu.com.cn/article/1",
                content="content",
                content_hash="hash",
                fetched_at="now",
            )
            self.assertEqual(store.add_solution_references([reference, reference]), 1)
            refs = store.list_solution_references("1A")
            self.assertEqual(len(refs), 1)
            self.assertEqual(refs[0].title, "题解")

            self.assertEqual(store.get_solution_fetch_attempt("1A"), "")
            store.mark_solution_fetch_attempt("1A")
            self.assertTrue(store.get_solution_fetch_attempt("1A"))


if __name__ == "__main__":
    unittest.main()
