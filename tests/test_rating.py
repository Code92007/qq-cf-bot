import unittest

from qq_cf_bot.rating import accepted_rating_update, leaderboard_rating


class RatingTest(unittest.TestCase):
    def test_accepted_high_problem_gives_more_rating(self):
        low = accepted_rating_update(1500, 1500, 64)
        high = accepted_rating_update(1500, 2200, 64)
        self.assertGreater(high - 1500, low - 1500)

    def test_accepted_always_increases_rating(self):
        self.assertGreater(accepted_rating_update(2600, 1900, 64), 2600)

    def test_leaderboard_rating_uses_exponential_problem_points(self):
        hard_single = leaderboard_rating((2600,))
        one_2500 = leaderboard_rating((2500,))
        two_2500 = leaderboard_rating((2500, 2500))
        four_2400 = leaderboard_rating((2400,) * 4)
        five_2400 = leaderboard_rating((2400,) * 5)

        self.assertGreater(hard_single, one_2500)
        self.assertAlmostEqual(two_2500, hard_single, delta=0.001)
        self.assertAlmostEqual(four_2400, hard_single, delta=0.001)
        self.assertGreater(five_2400, hard_single)


if __name__ == "__main__":
    unittest.main()
