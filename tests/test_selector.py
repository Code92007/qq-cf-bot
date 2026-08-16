import unittest

from qq_cf_bot.models import CFProblem
from qq_cf_bot.selector import ProblemSelector


class SelectorTest(unittest.TestCase):
    def test_filters_rating_and_sent_ids(self):
        problems = [
            CFProblem(1, "A", "too easy", 1800),
            CFProblem(2, "B", "ok", 1900),
            CFProblem(3, "C", "sent", 2200),
            CFProblem(4, "D", "too hard", 2700),
        ]
        selected = ProblemSelector(1900, 2600).candidates(problems, {"3C"})
        self.assertEqual([p.cf_id for p in selected], ["2B"])

    def test_shuffled_candidates_prefers_recent_contest_pool(self):
        problems = [
            CFProblem(1, "A", "old", 2000),
            CFProblem(100, "A", "new a", 2000),
            CFProblem(101, "A", "new b", 2000),
        ]

        selected = list(ProblemSelector(1900, 2600, recent_pool_size=2).shuffled_candidates(problems, set()))

        self.assertEqual({problem.cf_id for problem in selected}, {"100A", "101A"})


if __name__ == "__main__":
    unittest.main()
