import logging

from src.bot.base import Bot
from src.settings import config


def send_message(message: str, bots: list):
    for bot in bots:
        try:
            token = config.BOTS[bot.upper()]["TOKEN"]
            group = config.BOTS[bot.upper()]["GROUP_ID"]
            Bot(token).bot.send_message(
                group, message, parse_mode="html", disable_web_page_preview=True
            )
            logging.info(msg=f"sended: {message} to {bot} bot")
        except Exception as e:
            logging.error(
                msg=f'failed while sendind "{message}" to {bot} bot \n with exception: \n {e}'
            )
