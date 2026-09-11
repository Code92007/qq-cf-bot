import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace

from qq_cf_bot.core import ChallengeActor, ChallengeService
from qq_cf_bot.models import CFProblem, JudgeResult, ProblemStatement
from qq_cf_bot.storage import SentProblemStore


class _AcceptingJudge:
    configured = True

    def judge(self, *args, **kwargs):
        return JudgeResult(True, "思路正确。")


class _EmptySolutionBank:
    def ensure(self, problem, statement):
        return []

    def context_for_prompt(self, references, max_chars):
        return ""


class ChallengeServiceTest(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
