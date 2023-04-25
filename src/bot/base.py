import logging
import threading

import telebot
from django.apps import apps

from src.settings import config


class Bot(threading.Thread):
    def __init__(self, token, group=None):
        super().__init__()
        self.bot = telebot.TeleBot(token)
        self.group_id = group

        @self.bot.message_handler(commands=["balances"])
        def balances_handle(message):
            logging.info("run balances handler")
            response = ""
            network_model = apps.get_model("networks", "Network")

            for network in network_model.objects.all():
                balance = network.get_signer_balance()
                response += f"{network.name} balance is {float(balance) / 10 ** 18} {network.native_symbol} \n"

            self.bot.reply_to(message, response)

        @self.bot.message_handler(commands=["addresses"])
        def addresses_handle(message):
            logging.info("run addresses handler")
            self.bot.reply_to(message, config.SIGNER_ADDRESS)

        @self.bot.message_handler(commands=["ping"])
        def ping_handler(message):
            logging.info("run ping handler")
            self.bot.reply_to(message, "Pong")

    def run(self):
        self.bot.infinity_polling()
