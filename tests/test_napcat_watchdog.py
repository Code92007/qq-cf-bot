import importlib.util
import os
import unittest
from pathlib import Path
from unittest.mock import patch


_MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "napcat-watchdog.py"
_SPEC = importlib.util.spec_from_file_location("napcat_watchdog", _MODULE_PATH)
watchdog = importlib.util.module_from_spec(_SPEC)
assert _SPEC and _SPEC.loader
_SPEC.loader.exec_module(watchdog)


class NapcatWatchdogTest(unittest.TestCase):
    def test_url_candidates_include_docker_container_ip(self):
        env = {
            "NAPCAT_WATCHDOG_ONEBOT_URL": "http://127.0.0.1:3000",
            "ONEBOT_HTTP_URL": "http://napcat:3000",
            "NAPCAT_WATCHDOG_DOCKER_SERVICE": "napcat",
            "NAPCAT_WATCHDOG_DOCKER_PORT": "3000",
        }
        with patch.dict(os.environ, env, clear=True):
            with patch.object(watchdog, "_docker_container_ips", return_value=("172.20.0.3",)):
                candidates = watchdog._watchdog_base_url_candidates()

        self.assertEqual(
            candidates,
            (
                "http://127.0.0.1:3000",
                "http://napcat:3000",
                "http://172.20.0.3:3000",
            ),
        )

    def test_recent_offline_log_overrides_api_health(self):
        env = {
            "NAPCAT_WATCHDOG_LOG_CHECK_ENABLED": "true",
            "NAPCAT_WATCHDOG_DOCKER_SERVICE": "napcat",
        }
        logs = "napcat | 08-21 16:38:46 [info] Yzm007 | 账号状态变更为离线"
        with patch.dict(os.environ, env, clear=True):
            with patch.object(watchdog, "_check_napcat_api", return_value=(True, "api OK")):
                with patch.object(watchdog, "_run_quiet", return_value=logs):
                    ok, detail = watchdog.check_napcat()

        self.assertFalse(ok)
        self.assertIn("api OK", detail)
        self.assertIn("账号状态变更为离线", detail)

    def test_recent_good_log_after_error_is_healthy(self):
        env = {
            "NAPCAT_WATCHDOG_LOG_CHECK_ENABLED": "true",
            "NAPCAT_WATCHDOG_DOCKER_SERVICE": "napcat",
        }
        logs = "\n".join(
            [
                "napcat | 08-21 16:29:16 [error] [Core] [Login] Login Error,ErrType: 1 ErrCode: 3",
                "napcat | HTTP上报服务: http://qq-cf-bot:8088/onebot, : 已启动",
            ]
        )
        with patch.dict(os.environ, env, clear=True):
            with patch.object(watchdog, "_check_napcat_api", return_value=(True, "api OK")):
                with patch.object(watchdog, "_run_quiet", return_value=logs):
                    ok, detail = watchdog.check_napcat()

        self.assertTrue(ok)
        self.assertIn("recent NapCat log reports online", detail)


if __name__ == "__main__":
    unittest.main()
