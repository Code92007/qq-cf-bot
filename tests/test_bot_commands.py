import unittest

from qq_cf_bot.bot import _parse_rating_range


class BotCommandTest(unittest.TestCase):
    def test_parse_rating_range(self):
        self.assertEqual(_parse_rating_range("1900 2600"), (1900, 2600))
        self.assertEqual(_parse_rating_range("rating 2100-2400"), (2100, 2400))
        self.assertEqual(_parse_rating_range("2600 1900"), (1900, 2600))

    def test_reject_invalid_rating_range(self):
        self.assertIsNone(_parse_rating_range(""))
        self.assertIsNone(_parse_rating_range("abc"))
        self.assertIsNone(_parse_rating_range("700 2600"))
        self.assertIsNone(_parse_rating_range("1900 5000"))


if __name__ == "__main__":
    unittest.main()
