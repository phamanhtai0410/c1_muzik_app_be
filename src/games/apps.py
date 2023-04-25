import os

from django.apps import AppConfig


class GamesConfig(AppConfig):
    name = "src.games"

    def ready(self):
        from . import signals, signals_definition
