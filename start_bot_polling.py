import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "src.settings")
import django

django.setup()

from src.bot.base import Bot
from src.settings import config

if __name__ == "__main__":
    for value in config.BOTS.values():
        bot = Bot(value["TOKEN"], value["GROUP_ID"])
        bot.start()
