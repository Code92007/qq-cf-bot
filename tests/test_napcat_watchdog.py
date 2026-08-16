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


if __name__ == "__main__":
    unittest.main()
