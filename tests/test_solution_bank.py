import tempfile
import unittest
from pathlib import Path

from qq_cf_bot.models import CFProblem, ProblemStatement, SolutionReference
from qq_cf_bot.solution_bank import SolutionBank, _extract_luogu_solution_candidates
from qq_cf_bot.storage import SentProblemStore


class _FakeLuogu:
    def fetch_solution_payload(self, problem):
        return {
            "currentData": {
                "solutions": {
                    "result": [
                        {
                            "title": "树上差分",
                            "author": {"name": "alice"},
                            "id": "abc",
                            "content": "这是一份足够长的洛谷题解。" * 10,
                        }
                    ]
                }
            }
        }


class _FakeRemoteJudge:
    configured = False


class _FakeGeneratedSolution:
    title = "模型参考"
    content = "这是模型生成的参考解法，包含算法思路、正确性说明、复杂度分析和边界条件。" * 3


class _FakeSolutionGenerator:
    configured = True

    def __init__(self):
        self.calls = 0

    def generate(self, problem, statement):
        self.calls += 1
        return _FakeGeneratedSolution()


class SolutionBankTest(unittest.TestCase):
    def test_extracts_nested_luogu_solution_candidates(self):
        candidates = _extract_luogu_solution_candidates(
            {
                "data": {
                    "items": [
                        {
                            "title": "题解 A",
                            "user": {"username": "bob"},
                            "content": "动态规划做法。" * 20,
                        }
                    ]
                }
            }
        )
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].title, "题解 A")
        self.assertEqual(candidates[0].author, "bob")

    def test_ensure_caches_luogu_solution_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = SentProblemStore(Path(tmp) / "bot.sqlite3")
            bank = SolutionBank(
                store=store,
                luogu=_FakeLuogu(),
                remote_judge=_FakeRemoteJudge(),
                fetch_cf_editorial=False,
            )
            problem = CFProblem(1, "A", "Theatre Square", 1000)
            refs = bank.ensure(problem)
            self.assertEqual(len(refs), 1)
            self.assertEqual(refs[0].source, "luogu")

            cached = bank.ensure(problem)
            self.assertEqual(len(cached), 1)

    def test_generates_and_caches_llm_solution_when_public_refs_are_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = SentProblemStore(Path(tmp) / "bot.sqlite3")
            generator = _FakeSolutionGenerator()
            bank = SolutionBank(
                store=store,
                luogu=_FakeLuogu(),
                remote_judge=_FakeRemoteJudge(),
                solution_generator=generator,
                fetch_luogu=False,
                fetch_cf_editorial=False,
            )
            problem = CFProblem(28, "D", "Don't fear, DravDe is kind", 2400)
            statement = ProblemStatement(
                pid="CF28D",
                title="题目",
                description="题面",
                input_format="输入",
                output_format="输出",
                samples=[],
            )

            refs = bank.ensure(problem, statement)
            cached = bank.ensure(problem, statement)

            self.assertEqual(generator.calls, 1)
            self.assertEqual(len(refs), 1)
            self.assertEqual(refs[0].source, "llm_generated")
            self.assertEqual(cached[0].source, "llm_generated")

    def test_context_for_prompt_respects_limit(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = SentProblemStore(Path(tmp) / "bot.sqlite3")
            bank = SolutionBank(store, _FakeLuogu(), _FakeRemoteJudge())
            refs = [
                SolutionReference("1A", "luogu", "题解", "alice", "url", "x" * 1000, "hash"),
            ]
            context = bank.context_for_prompt(refs, max_chars=200)
            self.assertLessEqual(len(context), 260)
            self.assertIn("参考题解 1", context)


if __name__ == "__main__":
    unittest.main()
