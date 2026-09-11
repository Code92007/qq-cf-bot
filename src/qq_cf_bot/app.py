from __future__ import annotations

import logging

from .bot import CodeforcesPushBot
from .config import Config
from .server import OneBotEventServer
from .webapp import WebApplication


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )
    config = Config.from_env()
    bot = CodeforcesPushBot(config)
    web_app = WebApplication(config, bot.challenge_service)
    server = OneBotEventServer(
        config.host,
        config.port,
        bot.handle_group_message,
        access_token=config.onebot_event_access_token,
        web_app=web_app,
    )
    server.serve_forever()


if __name__ == "__main__":
    main()
