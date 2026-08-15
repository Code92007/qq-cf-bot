import os
import unittest
from unittest.mock import patch

from qq_cf_bot.config import Config


class ConfigTest(unittest.TestCase):
    def test_cf_submit_auto_enables_when_account_is_configured(self):
        with patch.dict(os.environ, {"CF_USERNAME": "tourist", "CF_PASSWORD": "secret"}, clear=True):
            config = Config.from_env()

        self.assertTrue(config.cf_submit_enabled)
        self.assertEqual(config.cf_handle, "tourist")

    def test_cf_submit_auto_stays_disabled_without_account(self):
        with patch.dict(os.environ, {"CF_SUBMIT_ENABLED": "auto"}, clear=True):
            config = Config.from_env()

        self.assertFalse(config.cf_submit_enabled)

    def test_cf_submit_false_forces_disabled_even_with_account(self):
        with patch.dict(
            os.environ,
            {"CF_SUBMIT_ENABLED": "false", "CF_USERNAME": "tourist", "CF_PASSWORD": "secret"},
            clear=True,
        ):
            config = Config.from_env()

        self.assertFalse(config.cf_submit_enabled)

    def test_cf_submit_rejects_unknown_enabled_value(self):
        with patch.dict(os.environ, {"CF_SUBMIT_ENABLED": "maybe"}, clear=True):
            with self.assertRaisesRegex(ValueError, "CF_SUBMIT_ENABLED"):
                Config.from_env()


if __name__ == "__main__":
    unittest.main()
