from __future__ import annotations

import logging

from .config import Config
from .core import ChallengeService
from .submitter import RemoteSubmissionError


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    config = Config.from_env()
    service = ChallengeService(config)
    if not service.remote_judge.configured and service.code_judge_available:
        print("OK: 远端提交载具未配置，代码提交将使用大模型静态审核兜底")
        return
    try:
        message = service.remote_judge.verify_login()
    except RemoteSubmissionError as exc:
        print(f"FAILED: {exc}")
        raise SystemExit(1) from exc
    print(f"OK: {message}")


if __name__ == "__main__":
    main()
