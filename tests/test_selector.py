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


if __name__ == "__main__":
    unittest.main()
