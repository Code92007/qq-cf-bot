import unittest

from qq_cf_bot.rating import accepted_rating_update


class RatingTest(unittest.TestCase):
    def test_accepted_high_problem_gives_more_rating(self):
        low = accepted_rating_update(1500, 1500, 64)
        high = accepted_rating_update(1500, 2200, 64)
        self.assertGreater(high - 1500, low - 1500)

    def test_accepted_always_increases_rating(self):
        self.assertGreater(accepted_rating_update(2600, 1900, 64), 2600)


if __name__ == "__main__":
    unittest.main()
