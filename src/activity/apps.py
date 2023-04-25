import os

from django.apps import AppConfig


class ActivityConfig(AppConfig):
    name = "src.activity"

    def ready(self):
        from . import signals

        if os.getenv("USE_WS") and os.getenv("USE_WS") == "True":
            from . import signals_ws
