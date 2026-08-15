from __future__ import annotations

import logging

from .bot import CodeforcesPushBot
from .config import Config
from .server import OneBotEventServer


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )
    config = Config.from_env()
    bot = CodeforcesPushBot(config)
    server = OneBotEventServer(config.host, config.port, bot.handle_group_message)
    server.serve_forever()


if __name__ == "__main__":
    main()
