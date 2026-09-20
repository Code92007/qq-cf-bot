import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace

from qq_cf_bot.core import ChallengeActor, ChallengeError, ChallengeService
from qq_cf_bot.models import (
    CFProblem,
    CodeSubmission,
    JudgeResult,
    PreparedProblem,
    ProblemStatement,
    RatingRange,
    RemoteJudgeResult,
)
from qq_cf_bot.storage import SentProblemStore
from qq_cf_bot.submitter import CodeforcesSubmissionError


class _AcceptingJudge:
    configured = True

    def judge(self, *args, **kwargs):
        return JudgeResult(True, "思路正确。")


class _EmptySolutionBank:
    def ensure(self, problem, statement):
        return []

    def context_for_prompt(self, references, max_chars):
        return ""


class _FailingRemoteJudge:
    configured = True
    last_submit_at = 0.0

    def judge(self, *args, **kwargs):
        raise CodeforcesSubmissionError("Codeforces 登录验证失败。")


class _ResultRemoteJudge:
    configured = True
    last_submit_at = 123.0

    def __init__(self, result):
        self.result = result

    def judge(self, *args, **kwargs):
        return self.result


class _CodeFallbackJudge:
    configured = True

    def __init__(self, accepted=True):
        self.accepted = accepted
        self.calls = 0

    def judge_code(self, *args, **kwargs):
        self.calls += 1
        return JudgeResult(self.accepted, "通过" if self.accepted else "边界条件处理错误。")


class _FailingTranslator:
    configured = True

    def translate_statement(self, statement):
        del statement
        raise RuntimeError("translation service is down")

    def translate_title(self, title):
        del title
        raise RuntimeError("translation service is down")


class _FailingJudge:
    configured = True

    def judge(self, *args, **kwargs):
        raise RuntimeError("judge service is down")


class ChallengeServiceTest(unittest.TestCase):
    def test_oral_judge_failure_returns_specific_service_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = ChallengeService.__new__(ChallengeService)
            service.config = SimpleNamespace(judge_solution_context_max_chars=1000)
            service.store = SentProblemStore(Path(tmp) / "bot.sqlite3")
            service.judge = _FailingJudge()
            service.solution_bank = _EmptySolutionBank()
            problem = CFProblem(1, "A", "Theatre Square", 1000)
            statement = ProblemStatement("1A", "剧院广场", "题面", "输入", "输出", [])
            service.store.set_active_problem(1, problem, statement, [], ranked=True)
            actor = ChallengeActor(scope_id=1, leaderboard_id=1, user_id=1, display_name="Alice")

            with self.assertRaises(ChallengeError) as caught:
                service.submit_solution(actor, "直接计算答案。")

            self.assertEqual(caught.exception.code, "judge_unavailable")
            self.assertEqual(caught.exception.status, 503)
            self.assertIsNotNone(service.store.get_active_problem(1))

    def test_statement_translation_failure_falls_back_to_source_statement(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = ChallengeService.__new__(ChallengeService)
            service.store = SentProblemStore(Path(tmp) / "bot.sqlite3")
            service.translator = _FailingTranslator()
            problem = CFProblem(1, "A", "Theatre Square", 1000)
            statement = ProblemStatement(
                "1A",
                "Theatre Square",
                (
                    "You are given a rectangular square in the city center. "
                    "Find the minimum number of stones needed to cover it completely."
                ),
                "Read three positive integers from standard input.",
                "Print the minimum number of stones.",
                [],
            )

            result = service._translate_and_cache_if_needed(problem, statement, source="codeforces")

            self.assertEqual(result, statement)
            self.assertEqual(service.store.get_cached_statement("1A"), statement)
            self.assertIsNone(service.store.get_cached_statement("1A", require_translated=True))

    def test_find_problem_rejects_unknown_problem(self):
        service = ChallengeService.__new__(ChallengeService)
        service.cf = SimpleNamespace(resolve_problem=lambda contest_id, index: None)

        with self.assertRaises(ChallengeError) as caught:
            service.find_problem(9999999, "Z")

        self.assertEqual(caught.exception.code, "problem_not_found")
        self.assertEqual(caught.exception.status, 404)

    def test_specific_problem_is_activated_without_ranking_or_dedup(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = ChallengeService.__new__(ChallengeService)
            service.store = SentProblemStore(Path(tmp) / "bot.sqlite3")
            problem = CFProblem(1704, "F", "Colouring Game", 2400)
            statement = ProblemStatement("CF1704F", "染色游戏", "题面", "输入", "输出", [])
            prepared = PreparedProblem(problem, statement, [], RatingRange(2400, 2400), "now")
            service.find_problem = lambda contest_id, index: problem
            service.prepare_specific_problem = lambda selected: prepared

            active = service.issue_specific_problem(123, 1704, "f")

            self.assertEqual(active.problem.cf_id, "1704F")
            self.assertFalse(active.ranked)
            self.assertEqual(service.store.sent_ids(123), set())
            with self.assertRaises(ChallengeError) as caught:
                service.issue_specific_problem(123, 1704, "F")
            self.assertEqual(caught.exception.code, "active_problem")

    def test_personal_scope_settles_into_shared_leaderboard(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = ChallengeService.__new__(ChallengeService)
            service.config = SimpleNamespace(
                judge_solution_context_max_chars=1000,
                initial_rating=1500.0,
                rating_k_factor=64.0,
            )
            service.store = SentProblemStore(Path(tmp) / "bot.sqlite3")
            service.judge = _AcceptingJudge()
            service.solution_bank = _EmptySolutionBank()
            service._submit_lock = threading.Lock()

            problem = CFProblem(1, "A", "Theatre Square", 1000, ("math",))
            statement = ProblemStatement("CF1A", "剧院广场", "题面", "输入", "输出", [])
            scope_id = -1_000_000_000_001
            service.store.mark_sent(scope_id, problem)
            service.store.set_active_problem(scope_id, problem, statement, [], ranked=True)
            actor = ChallengeActor(scope_id=scope_id, leaderboard_id=-1, user_id=1, display_name="Alice")

            outcome = service.submit_solution(actor, "直接计算覆盖块数。")

            self.assertTrue(outcome.accepted)
            self.assertIsNone(service.store.get_active_problem(scope_id))
            self.assertEqual(outcome.stat.solved_count, 1)
            self.assertEqual(service.store.list_group_stats(-1)[0].display_name, "Alice")
            self.assertEqual(service.store.list_group_stats(-1)[0].solved_ratings, (1000,))

    def test_failed_remote_submit_keeps_problem_and_does_not_start_cooldown(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = ChallengeService.__new__(ChallengeService)
            service.config = SimpleNamespace(
                code_submit_enabled=True,
                code_submit_llm_fallback=False,
                cf_submit_min_interval_seconds=180,
            )
            service.store = SentProblemStore(Path(tmp) / "bot.sqlite3")
            service.remote_judge = _FailingRemoteJudge()
            service.judge = _CodeFallbackJudge()
            service._submit_lock = threading.Lock()

            problem = CFProblem(1, "A", "Theatre Square", 1000)
            statement = ProblemStatement("CF1A", "剧院广场", "题面", "输入", "输出", [])
            service.store.set_active_problem(1, problem, statement, [], ranked=True)
            actor = ChallengeActor(scope_id=1, leaderboard_id=1, user_id=1, display_name="Alice")

            with self.assertRaises(ChallengeError) as caught:
                service.submit_code(actor, CodeSubmission("cpp", "int main(){}"))

            self.assertEqual(caught.exception.code, "code_submit_failed")
            self.assertEqual(caught.exception.status, 502)
            self.assertIsNotNone(service.store.get_active_problem(1))
            self.assertEqual(service.store.get_meta_float("cf_last_submit_at", 0.0), 0.0)

    def test_remote_failure_uses_llm_fallback_and_settles(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = self._code_service(tmp, _FailingRemoteJudge(), _CodeFallbackJudge(accepted=True))
            actor = self._activate_code_problem(service)

            outcome = service.submit_code(actor, CodeSubmission("cpp", "int main(){}"))

            self.assertTrue(outcome.accepted)
            self.assertEqual(outcome.remote_result.verdict, "LLM_ACCEPTED")
            self.assertIn("非 Codeforces/VJudge 运行结果", outcome.reason)
            self.assertIsNone(service.store.get_active_problem(1))
            self.assertEqual(outcome.stat.solved_count, 1)

    def test_final_remote_verdict_does_not_use_llm_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            remote = _ResultRemoteJudge(RemoteJudgeResult(False, "WRONG_ANSWER", "Wrong answer on test 2"))
            fallback = _CodeFallbackJudge(accepted=True)
            service = self._code_service(tmp, remote, fallback)
            actor = self._activate_code_problem(service)

            outcome = service.submit_code(actor, CodeSubmission("cpp", "int main(){}"))

            self.assertFalse(outcome.accepted)
            self.assertEqual(outcome.remote_result.verdict, "WRONG_ANSWER")
            self.assertEqual(fallback.calls, 0)
            self.assertIsNotNone(service.store.get_active_problem(1))

    def test_pending_remote_verdict_uses_fallback_and_keeps_remote_link(self):
        with tempfile.TemporaryDirectory() as tmp:
            remote = _ResultRemoteJudge(
                RemoteJudgeResult(
                    False,
                    "PENDING",
                    "代码已提交，但轮询超时。",
                    submission_id=42,
                    url="https://vjudge.net/solution/42",
                )
            )
            fallback = _CodeFallbackJudge(accepted=False)
            service = self._code_service(tmp, remote, fallback)
            actor = self._activate_code_problem(service)

            outcome = service.submit_code(actor, CodeSubmission("cpp", "int main(){}"))

            self.assertFalse(outcome.accepted)
            self.assertEqual(outcome.remote_result.verdict, "LLM_REJECTED")
            self.assertEqual(outcome.remote_result.submission_id, 42)
            self.assertEqual(outcome.remote_result.url, "https://vjudge.net/solution/42")
            self.assertEqual(fallback.calls, 1)

    def _code_service(self, tmp, remote_judge, fallback_judge):
        service = ChallengeService.__new__(ChallengeService)
        service.config = SimpleNamespace(
            code_submit_enabled=True,
            code_submit_llm_fallback=True,
            cf_submit_min_interval_seconds=0,
            judge_solution_context_max_chars=1000,
            initial_rating=1500.0,
            rating_k_factor=64.0,
        )
        service.store = SentProblemStore(Path(tmp) / "bot.sqlite3")
        service.remote_judge = remote_judge
        service.judge = fallback_judge
        service.solution_bank = _EmptySolutionBank()
        service._submit_lock = threading.Lock()
        return service

    def _activate_code_problem(self, service):
        problem = CFProblem(1, "A", "Theatre Square", 1000)
        statement = ProblemStatement("CF1A", "剧院广场", "题面", "输入", "输出", [])
        service.store.set_active_problem(1, problem, statement, [], ranked=True)
        return ChallengeActor(scope_id=1, leaderboard_id=1, user_id=1, display_name="Alice")


if __name__ == "__main__":
    unittest.main()
