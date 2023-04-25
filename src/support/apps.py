from django.apps import AppConfig


class SupportConfig(AppConfig):
    name = "src.support"

    def ready(self):
        from . import signals
