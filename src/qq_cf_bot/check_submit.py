from __future__ import annotations

import logging

from .config import Config
from .core import ChallengeService
from .submitter import CodeforcesSubmissionError


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    config = Config.from_env()
    service = ChallengeService(config)
    try:
        message = service.remote_judge.verify_login()
    except CodeforcesSubmissionError as exc:
        print(f"FAILED: {exc}")
        raise SystemExit(1) from exc
    print(f"OK: {message}")


if __name__ == "__main__":
    main()
